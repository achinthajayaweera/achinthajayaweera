import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree

HEADERS = {'authorization': 'token ' + os.environ['ACCESS_TOKEN']}
USER_NAME = 'achinthajayaweera'


def daily_readme(birthday):
    """Returns age as 'XX years, XX months, XX days'"""
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        diff.years, 'year' + ('s' if diff.years != 1 else ''),
        diff.months, 'month' + ('s' if diff.months != 1 else ''),
        diff.days, 'day' + ('s' if diff.days != 1 else ''),
        ' 🎂' if (diff.months == 0 and diff.days == 0) else '')


def simple_request(query, variables):
    r = requests.post('https://api.github.com/graphql',
                      json={'query': query, 'variables': variables},
                      headers=HEADERS)
    if r.status_code == 200:
        return r
    raise Exception(f'GraphQL request failed: {r.status_code} {r.text}')


def get_user_stats():
    query = '''
    query($login: String!) {
        user(login: $login) {
            repositories(first: 100, ownerAffiliations: OWNER) {
                totalCount
                edges {
                    node {
                        stargazers { totalCount }
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history(first: 1) { totalCount }
                                }
                            }
                        }
                    }
                }
            }
            contributionsCollection {
                totalCommitContributions
                restrictedContributionsCount
            }
            followers { totalCount }
            repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
                totalCount
            }
        }
    }'''
    r = simple_request(query, {'login': USER_NAME})
    data = r.json()['data']['user']

    repos = data['repositories']['totalCount']
    stars = sum(e['node']['stargazers']['totalCount'] for e in data['repositories']['edges'])
    commits = (data['contributionsCollection']['totalCommitContributions'] +
               data['contributionsCollection']['restrictedContributionsCount'])
    followers = data['followers']['totalCount']
    contributed = data['repositoriesContributedTo']['totalCount']

    return repos, stars, commits, followers, contributed


def find_and_replace(root, element_id, new_text):
    el = root.find(f".//*[@id='{element_id}']")
    if el is not None:
        el.text = str(new_text)


def justify_format(root, element_id, new_text, length=0):
    if isinstance(new_text, int):
        new_text = '{:,}'.format(new_text)
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_map = {0: '', 1: ' ', 2: '. '}
        dot_string = dot_map[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f'{element_id}_dots', dot_string)


def svg_overwrite(filename, age_data, repos, stars, commits, followers, contributed):
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, 'age_data', age_data, 27)
    justify_format(root, 'repo_data', repos, 4)
    justify_format(root, 'contrib_data', contributed)
    justify_format(root, 'star_data', stars, 14)
    justify_format(root, 'commit_data', commits, 22)
    justify_format(root, 'follower_data', followers, 10)
    tree.write(filename, encoding='utf-8', xml_declaration=True)
    print(f'Updated {filename}')


if __name__ == '__main__':
    # Birthday: 28 October 2002
    age = daily_readme(datetime.datetime(2002, 10, 28))
    print(f'Age: {age}')

    repos, stars, commits, followers, contributed = get_user_stats()
    print(f'Repos: {repos}, Stars: {stars}, Commits: {commits}, Followers: {followers}, Contributed: {contributed}')

    svg_overwrite('dark_mode.svg', age, repos, stars, commits, followers, contributed)
    svg_overwrite('light_mode.svg', age, repos, stars, commits, followers, contributed)
    print('Done!')
