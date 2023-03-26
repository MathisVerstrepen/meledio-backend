import unittest
import requests
import json

class TestApi(unittest.TestCase):

    def setUp(self):
        self.base_url = 'http://65.21.91.39:5100/'
        self.headers = {"Authorization": "Bearer uAJRzpD5JQK8o8pHN7YsajXW6DoHmdoS"}
        
        with open('test_data.json') as f:
            self.test_data = json.load(f)
        
    def test_00_matching_games_endpoint(self):
        print('-- Testing matching_games endpoint --')
        expected_data_list = self.test_data['matching_games']
        for i, (game_title, expected_data) in enumerate(expected_data_list.items()):
            url = self.base_url + f'matching_games?game={game_title}'
            response = requests.get(url, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            actual_data = json.loads(response.text)
            try:
                self.assertDictEqual(actual_data, expected_data)
                print(f'Test {i+1} ({game_title}) : \033[92mPASSED\033[0m')
            except AssertionError:
                print(f'Test {i+1} ({game_title}) : \033[91mFAILED\033[0m')
                print(f'Difference : {self.diff_dicts(expected_data, actual_data)}')
                assert False
                
    def test_01_new_game_endpoint(self):
        print('-- Testing new_game endpoint --')
        expected_data_list = self.test_data['new_game']
        for i, (game_id, expected_data) in enumerate(expected_data_list.items()):
            url = self.base_url + f'new_game?gameID={game_id}'
            response = requests.post(url, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            actual_data = json.loads(response.text)
            try:
                self.assertDictEqual(actual_data, expected_data)
                print(f'Test {i+1} ({game_id}) : \033[92mPASSED\033[0m')
            except AssertionError:
                print(f'Test {i+1} ({game_id}) : \033[91mFAILED\033[0m')
                print(f'Difference : {self.diff_dicts(expected_data, actual_data)}')
                assert False
                
    def test_02_matching_videos_endpoint(self):
        print('-- Testing s1/match endpoint --')
        expected_data_list = self.test_data['s1/match']
        for i, (game_id, expected_data) in enumerate(expected_data_list.items()):
            url = self.base_url + f's1/match?gameID={game_id}'
            response = requests.get(url, headers=self.headers)
            try:
                self.assertEqual(response.status_code, 200)
                actual_data = json.loads(response.text)
                assert self.compare_dicts(actual_data, expected_data)
                print(f'Test {i+1} ({game_id}) : \033[92mPASSED\033[0m')
            except AssertionError:
                print(f'Test {i+1} ({game_id}) : \033[91mFAILED\033[0m')
                print(f'Difference : {self.diff_dicts(expected_data, actual_data)}')

    def diff_dicts(self, dict1, dict2):
        keys = set(dict1.keys()).union(set(dict2.keys()))
        diff = {}
        for key in keys:
            if dict1.get(key) != dict2.get(key):
                diff[key] = [dict1.get(key), dict2.get(key)]
        return diff
    
    def compare_dicts(self, dict1, dict2):
        """
        Compare two dictionaries, ignoring integer values.

        Returns True if the dictionaries have the same keys and non-integer values,
        or False otherwise.
        """
        # Get the keys from the first dictionary
        dict1_keys = set(dict1.keys())
        
        # Get the keys from the second dictionary
        dict2_keys = set(dict2.keys())

        # Compare the keys
        if dict1_keys != dict2_keys:
            return False

        # Compare the values
        for key in dict1_keys:
            if isinstance(dict1[key], dict):
                if not isinstance(dict2[key], dict):
                    print(f'isinstance({dict2[key]}, dict) returned False')
                    return False
                if not self.compare_dicts(dict1[key], dict2[key]):
                    print(f'compare_dicts({dict1[key]}, {dict2[key]}) returned False')
                    return False
            elif not isinstance(dict1[key], int) and dict1[key] != dict2[key]:
                print(f'isinstance({dict1[key]}, int) returned False and {dict1[key]} != {dict2[key]}')
                return False

        return True

if __name__ == '__main__':
    unittest.main(verbosity=0)