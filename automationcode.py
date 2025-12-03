import requests
import json
import os
from datetime import datetime, date
import sys

githupattoken = os.environ.get("GITHUB_PAT")
ERROR_CODE = 1


def getQueryDetails():
    url = "https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None

def get_github_issues(github_pat_token):
    if(github_pat_token!=None):
        url = f"https://api.github.ibm.com/repos/zCustomer-Test/USS-Automation/issues"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_pat_token}",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # raises exception for 4xx/5xx
            issues = response.json()
            return issues
        except requests.exceptions.RequestException as e:
            print("An exception occurred when getting the issues:", e)
            sys.exit(ERROR_CODE)
    else:
        print("GIT HUB PAT TOKEN IS NOT SET")

def is_date_in_current_week(check_date_str):
    try:
        check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            check_date = datetime.strptime(check_date_str, '%Y-%m-%d %H:%M:%S').date()
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS"
    
    today = date.today()
    
    current_week = today.isocalendar()[1]
    check_week = check_date.isocalendar()[1]
    current_year = today.isocalendar()[0]
    check_year = check_date.isocalendar()[0]
    
  
    is_current_week = (current_week == check_week) and (current_year == check_year)
    
    return is_current_week, f"Date {check_date_str} is {'in' if is_current_week else 'not in'} current week (week {current_week} of {current_year})"


if __name__ == "__main__":
    data = get_github_issues(githupattoken)
    if data:
        with open('output.json', 'w') as f:
            json.dump(data, f, indent=4)