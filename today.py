import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree

HEADERS = {'authorization': 'token ' + os.environ['ACCESS_TOKEN']}
USER_NAME = 'achinthajayaweera'


def daily_readme(birthday):
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        diff.years, 'year' + ('s' if diff.years != 1 else ''),
        diff.months, 'month' + ('s' if diff.months != 1 else ''),
        diff.days, 'day' + ('s' if diff.days != 1 else ''),
        ' 🎂' if (diff.months == 0 and diff.days == 0) else '')


def graphql(query, variables={}):
    r = requests.post('https://api.github.com/graphql',
                      json={'query': query, 'variables': variables},
                      headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    raise Exception(f'GraphQL failed: {r.status_code} {r.text}')


def get_stats():
    data = graphql('''
    query($login: String!) {
        user(login: $login) {
            repositories(first: 100, ownerAffiliations: OWNER) {
                totalCount
                edges { node { stargazers { totalCount } } }
            }
            contributionsCollection {
                totalCommitContributions
                restrictedContributionsCount
            }
            followers { totalCount }
            repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
                totalCount
            }
        }
    }''', {'login': USER_NAME})['data']['user']

    repos = data['repositories']['totalCount']
    stars = sum(e['node']['stargazers']['totalCount'] for e in data['repositories']['edges'])
    commits = (data['contributionsCollection']['totalCommitContributions'] +
               data['contributionsCollection']['restrictedContributionsCount'])
    followers = data['followers']['totalCount']
    contributed = data['repositoriesContributedTo']['totalCount']
    return repos, stars, commits, followers, contributed


def get_loc():
    """Get total lines of code added/deleted across all repos"""
    query = '''
    query($login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 50, after: $cursor, ownerAffiliations: OWNER) {
                edges {
                    node {
                        nameWithOwner
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history(first: 1) { totalCount }
                                }
                            }
                        }
                    }
                }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    # Simplified: return 0 for now, full LOC counting is very slow
    # The GitHub Action will update commits/followers/repos/stars in real time
    return 0, 0, 0


def find_replace(root, eid, text):
    el = root.find(f".//*[@id='{eid}']")
    if el is not None:
        el.text = str(text)


def justify(root, eid, val, length=0):
    if isinstance(val, int):
        val = '{:,}'.format(val)
    val = str(val)
    find_replace(root, eid, val)
    just_len = max(0, length - len(val))
    if just_len == 0: dot_str = ''
    elif just_len == 1: dot_str = ' '
    elif just_len == 2: dot_str = '. '
    else: dot_str = ' ' + ('.' * just_len) + ' '
    find_replace(root, f'{eid}_dots', dot_str)


def update_svg(filename, age, repos, stars, commits, followers, contributed, loc_add, loc_del, loc_net):
    tree = etree.parse(filename)
    root = tree.getroot()
    justify(root, 'age_data', age, 27)
    justify(root, 'repo_data', repos, 4)
    justify(root, 'contrib_data', contributed)
    justify(root, 'star_data', stars, 14)
    justify(root, 'commit_data', commits, 22)
    justify(root, 'follower_data', followers, 10)
    justify(root, 'loc_data', loc_net, 9)
    find_replace(root, 'loc_add', '{:,}'.format(loc_add))
    find_replace(root, 'loc_del', '{:,}'.format(loc_del))
    tree.write(filename, encoding='utf-8', xml_declaration=True)
    print(f'Updated: {filename}')


if __name__ == '__main__':
    age = daily_readme(datetime.datetime(2002, 10, 28))
    print(f'Age: {age}')

    repos, stars, commits, followers, contributed = get_stats()
    print(f'Repos:{repos} Stars:{stars} Commits:{commits} Followers:{followers} Contributed:{contributed}')

    loc_add, loc_del, loc_net = get_loc()

    update_svg('dark_mode.svg', age, repos, stars, commits, followers, contributed, loc_add, loc_del, loc_net)
    update_svg('light_mode.svg', age, repos, stars, commits, followers, contributed, loc_add, loc_del, loc_net)
    print('Done!')
