import json, ast
from datetime import datetime
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
from typing import Any, Dict
from pathlib import Path
import os
import re
import subprocess

JENKINSFILE_PATH = "Jenkinsfile2"

with open("config.json", "r") as f:
    config = json.load(f)

def normalize_date(s):
    if not isinstance(s, str) or not s.strip():
        return s
    s = s.strip()
    fmts = [
        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
        '%Y-%m-%d', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y'
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.isoformat()
        except Exception:
            pass
    return s

def clean_text_html(t):
    if t is None:
        return ''
    soup = BeautifulSoup(str(t), 'html.parser')
    return soup.get_text(separator='\n', strip=True)

def parse_dt(s):
    if not isinstance(s, str) or not s:
        return datetime.min
    try:
        return datetime.fromisoformat(s)
    except Exception:
        for fmt in (
            '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y'
        ):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return datetime.min

def process_response_file(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    inner_json_str = ast.literal_eval(raw_text)
    inner_obj = json.loads(inner_json_str)
    main_list = inner_obj.get('mainList', [])

    clean_items = []
    for item in main_list:
        new_item = {
            'id': item.get('_id'),
            'doctype': item.get('doctype'),
            'date': normalize_date(item.get('date')),
            'user': item.get('user'),
            'subject': item.get('subject'),
            'img': item.get('img'),
            'updateUser': item.get('updateUser'),
            'updateDate': normalize_date(item.get('updateDate')),
            'updateImg': item.get('updateImg'),
            'releases': item.get('release', []),
            'content': clean_text_html(item.get('content'))
        }
        
        clean_items.append(new_item)

    clean_obj = {'count': len(clean_items), 'items': clean_items}
    
    sorted_items = sorted(clean_items, key=lambda x: parse_dt(x.get('date')), reverse=True)
    sorted_obj = {'count': len(sorted_items), 'items': sorted_items}
    with open('response_sorted_by_date_desc.json', 'w', encoding='utf-8') as f:
        json.dump(sorted_obj, f, ensure_ascii=False, indent=2)

def getthedetails():
    filename = 'response_sorted_by_date_desc.json'
    output_filename = 'extracted_sections.txt'
    output_string = ''

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            first_array = data['items'][0]
            entry_date = datetime.fromisoformat(first_array['date'].replace('Z', '+00:00'))
            
            today = datetime.now()
            days_since_sunday = today.weekday()
            week_start = today - timedelta(days=days_since_sunday)
            week_end = week_start + timedelta(days=6)
            
            content = first_array['content']
            service_copy_message = first_array.get('subject')
            
            if week_start.date() <= entry_date.date() <= week_end.date():
                if content:
                    output_string+=content
                else:
                    print("No content found to write.")
            else:
                print(f"Entry date {entry_date} is NOT within the current week.")

        return output_string, entry_date, service_copy_message
                
    except FileNotFoundError:
        print(f"File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        return "", None

def login_to_ecobuild() -> Dict[str, Any]:
    user = os.environ.get("USER")
    pwd = os.environ.get("PASS")

    print("USER:",user)

    #check condition here
    if not user or not pwd:
        return {"success": False, "error": "Missing username or password"}

    payload = {"username": user, "password": pwd}
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(config["base_url"]+"apiLogin", json=payload, headers=headers,verify=False) # false to ignore SSL certificate verification
        resp.raise_for_status() 
        return {"success": True, "data": resp.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

def to_get_Weeklydetails(bearer_token):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.get(config["base_url"]+"postserv/accept", headers=headers, verify=False)
        resp.raise_for_status()
        data = resp.json()
        with open("response.json", "w") as f:
            json.dump(data, f, indent=2)
        return {"success": True, "data": data}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

def is_invalid_header(header,ignore_words):
    return any(w in header.lower() for w in ignore_words)

def is_valid_content(contents,ignore_words):
    for line in contents:
        l = line.lower().strip()
        if l and l not in ignore_words and not set(l) <= {"-", "="}:
            return True
    return False

def filter_output(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        input_data = f.read()
        lines = input_data.splitlines()
        ignore_words = ["none", "successful"]
        sections = {"APPLY": [], "ACCEPT": []}

        current_section = None
        current_version = None
        buffer = []

        for line in lines:
            line = line.rstrip()

            if line.strip() in sections:
                current_section = line.strip()
                continue

            if line.strip().startswith("z/OS"):
                if current_section and current_version and buffer:
                    if not is_invalid_header(current_version,ignore_words) and is_valid_content(buffer,ignore_words):
                        sections[current_section].append((current_version, buffer))

                current_version = line.strip()
                buffer = []

            else:
                if line.strip():
                    buffer.append(line.strip())

        if current_section and current_version and buffer:
            if not is_invalid_header(current_version,ignore_words) and is_valid_content(buffer,ignore_words):
                sections[current_section].append((current_version, buffer))


        for section in ["APPLY", "ACCEPT"]:
            print(f"Failures for {section} testing:")

            if not sections[section]:
                print("NONE\n")
            else:
                for version, contents in sections[section]:
                    print(version)
                    for c in contents:
                        print(c)
                    print()


def filter_output_from_string(input_data):
    lines = input_data.splitlines()
    ignore_words = ["none", "successful"]
    sections = {"APPLY": [], "ACCEPT": []}

    current_section = None
    current_version = None
    buffer = []

    for line in lines:
        line = line.rstrip()

        if line.strip() in sections:
            current_section = line.strip()
            continue

        if line.strip().startswith("z/OS"):
            if current_section and current_version and buffer:
                if (
                    not is_invalid_header(current_version, ignore_words)
                    and is_valid_content(buffer, ignore_words)
                ):
                    sections[current_section].append((current_version, buffer))

            current_version = line.strip()
            buffer = []

        else:
            if line.strip():
                buffer.append(line.strip())

    if current_section and current_version and buffer:
        if (
            not is_invalid_header(current_version, ignore_words)
            and is_valid_content(buffer, ignore_words)
        ):
            sections[current_section].append((current_version, buffer))

    output_lines = []

    for section in ["APPLY", "ACCEPT"]:
        output_lines.append(f"Failures for {section} testing:")

        if not sections[section]:
            output_lines.append("NONE")
            output_lines.append("")
        else:
            for version, contents in sections[section]:
                output_lines.append(version)
                for c in contents:
                    output_lines.append(c)
                output_lines.append("")

    return "\n".join(output_lines)


def generate_log_files(output_string):
    SCRIPT_DIR = Path(__file__).parent.resolve()
    print("Script Directory:",SCRIPT_DIR)
    LOG_DIR = SCRIPT_DIR / "logs"
    LOG_DIR.mkdir(exist_ok=True) 

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULT_FILE = LOG_DIR / f"ecobuild_trigger_{timestamp}.txt"

    with open(RESULT_FILE, "w") as f:
        f.write(output_string)

def cron_for_datetime(dt):
    return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"

# def update_jenkins_cron(next_run_dt):
#     cron_expr = cron_for_datetime(next_run_dt)

#     with open(JENKINSFILE_PATH, "r") as f:
#         content = f.read()

#     updated, count = re.subn(
#         r"cron\(['\"]([^'\"]+)['\"]\)",
#         f'cron("{cron_expr}")',
#         content
#     )

#     if count == 0:
#         raise RuntimeError("No cron trigger found in Jenkinsfile")

#     with open(JENKINSFILE_PATH, "w") as f:
#         f.write(updated)

#     print(f"[CRON] Updated Jenkins cron → {cron_expr}")


import re

def update_jenkins_cron(next_run_dt):
    cron_expr = cron_for_datetime(next_run_dt)

    with open(JENKINSFILE_PATH, "r") as f:
        content = f.read()

    match = re.search(r'cron\(["\'](.*?)["\']\)', content)
    if not match:
        raise RuntimeError("No cron trigger found in Jenkinsfile")

    current_cron = match.group(1)

    if current_cron.strip() == cron_expr.strip():
        print(f"[CRON] No change required → {cron_expr}")
        return False

    updated_content = re.sub(
        r'cron\(["\'].*?["\']\)',
        f'cron("{cron_expr}")',
        content,
        count=1
    )

    with open(JENKINSFILE_PATH, "w") as f:
        f.write(updated_content)

    print(f"[CRON] Updated Jenkins cron:")
    print(f"        OLD → {current_cron}")
    print(f"        NEW → {cron_expr}")

    return True

def compute_next_run(build_found, build_datetime=None):
    now = datetime.now()

    if build_found and build_datetime:
        days_ahead = (7 - build_datetime.weekday()) % 7 or 7
        next_monday = build_datetime + timedelta(days=days_ahead)
        # return next_monday.replace(hour=5, minute=30, second=0) #4pm ist
        return next_monday.replace(hour=9, minute=0, second=0) # 9AM

    # Build not found → retry in 3 hours
    return now + timedelta(hours=3)

def send_to_slack(slack_message):
    slack_key = os.environ.get("SLACK_KEY")
    slack_url = "https://hooks.slack.com/services/"+slack_key
    # slack_url = slack_key.replace('\u00a0', ' ')

    slack_channel="ecobuild-automation"

    slack_payload = {
    "text": f"\n```{slack_message}```\n",
    }

    if slack_channel is not None and slack_channel.strip() != "":
        slack_payload["channel"] = slack_channel

    response = requests.post(
        slack_url, data=json.dumps(slack_payload), verify=False
    )

    if response.status_code != 200:
        print("Unable to post to Slack.")
        print("Response: HTTP %s", response.status_code)
        print("Response content: %s", response.content)
        return False
    return True

if __name__ == '__main__':
    result = login_to_ecobuild()
    status = result.get("success")
    data = result.get("data")
    err = result.get("error")


    print(f"Status: {status}")
    if err:
        print(f"Error: {err}")
    else:
        print("Auth Token", data['token'])
        token = data['token']
        result = to_get_Weeklydetails(token)
        if result["success"]:
            print("Data is Saved in the Response.json file")
            process_response_file('response.json')

            output_string, entry_date , service_copy_message = getthedetails()

            build_found = bool(output_string and entry_date)

            if build_found:
                print("[INFO] Build found for current week")
                filter_output_string = filter_output_from_string(output_string)
                log_string = service_copy_message + "\n\n" + filter_output_string
                # generate_log_files(log_string) #pushing log files only if a new build is found
                print("LOG STRING:",log_string)
                # send_to_slack(log_string)
            else:
                print("[INFO] Build NOT found yet")
                # send_to_slack("[INFO] Build NOT found yet")

            next_run = compute_next_run(build_found, entry_date)
            # update_jenkins_cron(next_run)
            changed_cron = update_jenkins_cron(next_run)

            if not changed_cron:
                print("[INFO] Skipping commit since cron is unchanged")


        else:
            print(f"Error: {result['error']}")
