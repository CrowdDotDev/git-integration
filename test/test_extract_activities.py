# -*- coding: utf-8 -*-

from crowdgit.activity import extract_activities, extract_activities_fuzzy


def test_extract_activities():
    # Test with a well-formed commit message
    commit_message = [
        'Signed-off-by: Arnd Bergmann <arnd@arndb.de>',
        'Reported-by: Guenter Roeck <linux@roeck-us.net>',
        'Reviewed-by: Manivannan Sadhasivam <mani@kernel.org>',
        'Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>'
    ]

    expected_activities = [
        {'Co-authored-by': {'email': 'arnd@arndb.de', 'name': 'Arnd Bergmann'}},
        {'Signed-off-by': {'email': 'arnd@arndb.de', 'name': 'Arnd Bergmann'}},
        {'Reported-by': {'email': 'linux@roeck-us.net', 'name': 'Guenter Roeck'}},
        {'Reviewed-by': {'email': 'mani@kernel.org', 'name': 'Manivannan Sadhasivam'}},
        {'Co-authored-by': {'email': 'torvalds@linux-foundation.org',
                            'name': 'Linus Torvalds'}},
        {'Signed-off-by': {'email': 'torvalds@linux-foundation.org',
                           'name': 'Linus Torvalds'}}]
    assert extract_activities(commit_message) == expected_activities

    # Test with a lower case commit message and several typos
    commit_message = [
        'accked-by: John Doe <john.doe@example.com>',
        'acked-and-reviewed by: Jane Smith <jane.smith@example.com>',
        'acked and--reviewed by: Jane Smith <jane.smith@example.com>'
    ]
    expected_activities = [
        {'Reviewed-by': {'name': 'John Doe', 'email': 'john.doe@example.com'}},
    ]
    expected_activities_fuzzy = [
        {'Reviewed-by': {'name': 'John Doe', 'email': 'john.doe@example.com'}},
        {'Reviewed-by': {'name': 'Jane Smith', 'email': 'jane.smith@example.com'}},
        {'Reviewed-by': {'name': 'Jane Smith', 'email': 'jane.smith@example.com'}}
    ]
    assert extract_activities(commit_message) == expected_activities
    assert extract_activities_fuzzy(commit_message) == expected_activities_fuzzy

    # Test with an empty commit message
    commit_message = []
    expected_activities = []
    assert extract_activities(commit_message) == expected_activities

    # Test with a commit message without activities
    commit_message = [
        'This is a commit message without any activities.',
        'It has multiple lines, but none of them contain activities.'
    ]
    expected_activities = []
    assert extract_activities(commit_message) == expected_activities
