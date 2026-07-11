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
    # Get all years user has been on GitHub
    data = graphql('''
    query($login: String!) {
        user(login: $login) {
            createdAt
            repositories(first: 100, ownerAffiliations: OWNER) {
                totalCount
                edges {
                    node {
                        stargazers { totalCount }
                        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                            edges { size node { name } }
                        }
                        object(expression: "HEAD") {
                            ... on Commit {
                                history { totalCount }
                            }
                        }
                    }
                }
            }
            followers { totalCount }
            repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
                totalCount
            }
        }
    }''', {'login': USER_NAME})['data']['user']

    repos = data['repositories']['totalCount']
    stars = sum(e['node']['stargazers']['totalCount'] for e in data['repositories']['edges'])
    followers = data['followers']['totalCount']
    contributed = data['repositoriesContributedTo']['totalCount']
    created_at = data['createdAt'][:4]  # year joined

    return repos, stars, followers, contributed, int(created_at)


def get_total_contributions(year_joined):
    """Sum contributions across all years"""
    total = 0
    current_year = datetime.datetime.today().year
    for year in range(year_joined, current_year + 1):
        start = f'{year}-01-01T00:00:00Z'
        end = f'{year}-12-31T23:59:59Z'
        data = graphql('''
        query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar { totalContributions }
                }
            }
        }''', {'login': USER_NAME, 'from': start, 'to': end})
        year_total = data['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
        total += year_total
        print(f'  {year}: {year_total} contributions')
    return total


def get_loc():
    """Count total lines of code added/deleted across all repos"""
    query = '''
    query($login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, ownerAffiliations: OWNER, after: $cursor) {
                edges { node { nameWithOwner } }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    repos = []
    cursor = None
    while True:
        data = graphql(query, {'login': USER_NAME, 'cursor': cursor})['data']['user']['repositories']
        repos += [e['node']['nameWithOwner'] for e in data['edges']]
        if not data['pageInfo']['hasNextPage']:
            break
        cursor = data['pageInfo']['endCursor']

    loc_add = loc_del = 0
    for repo in repos:
        try:
            r = requests.get(
                f'https://api.github.com/repos/{repo}/stats/contributors',
                headers=HEADERS, timeout=10)
            if r.status_code == 200 and r.json():
                for contributor in r.json():
                    if contributor.get('author', {}).get('login', '').lower() == USER_NAME.lower():
                        for week in contributor.get('weeks', []):
                            loc_add += week.get('a', 0)
                            loc_del += week.get('d', 0)
        except Exception as e:
            print(f'  LOC error for {repo}: {e}')
    loc_net = loc_add - loc_del
    return loc_add, loc_del, loc_net


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


def update_svg(filename, age, repos, stars, contributions, followers, contributed, loc_add, loc_del, loc_net):
    tree = etree.parse(filename)
    root = tree.getroot()
    justify(root, 'age_data', age, 27)
    justify(root, 'repo_data', repos, 4)
    justify(root, 'contrib_data', contributed)
    justify(root, 'star_data', stars, 10)
    justify(root, 'commit_data', contributions, 15)
    justify(root, 'follower_data', followers, 8)
    justify(root, 'loc_data', '{:,}'.format(loc_net), 9)
    find_replace(root, 'loc_add', '{:,}'.format(loc_add))
    find_replace(root, 'loc_del', '{:,}'.format(loc_del))
    tree.write(filename, encoding='utf-8', xml_declaration=True)
    print(f'Updated: {filename}')


if __name__ == '__main__':
    age = daily_readme(datetime.datetime(2002, 10, 28))
    print(f'Age: {age}')

    repos, stars, followers, contributed, year_joined = get_stats()
    print(f'Repos:{repos} Stars:{stars} Followers:{followers} Contributed:{contributed} Joined:{year_joined}')

    print('Counting total contributions...')
    total_contributions = get_total_contributions(year_joined)
    print(f'Total contributions: {total_contributions}')

    print('Counting lines of code...')
    loc_add, loc_del, loc_net = get_loc()
    print(f'LOC: +{loc_add:,} -{loc_del:,} net:{loc_net:,}')

    update_svg('dark_mode.svg', age, repos, stars, total_contributions, followers, contributed, loc_add, loc_del, loc_net)
    update_svg('light_mode.svg', age, repos, stars, total_contributions, followers, contributed, loc_add, loc_del, loc_net)
    print('Done!')
