import requests
import json

# Define the API endpoint and headers
url = "https://api.x.ai/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer xai-da7pVmPJ5frkiun08Z9gW2uLuxvm7Dyt15ieESbJoN82xk4SudhwermLUkO9YxuY02J6U4vW0pOR2ylL"
}

# Prompt the user for the payload contents
system_content = input("Enter the system content: ")
user_content = input("Enter the user content: ")

# Define the payload
payload = {
    "messages": [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user",
            "content": user_content
        }
    ],
    "model": "grok-beta",
    "stream": False,
    "temperature": 0
}

# Make the POST request
response = requests.post(url, headers=headers, data=json.dumps(payload))

# Print the message part of the response
if response.status_code == 200:
    response_json = response.json()
    if 'choices' in response_json and len(response_json['choices']) > 0:
        message = response_json['choices'][0]['message']['content']
        print("Message:\n", message)
    else:
        print("No message found in the response.")
else:
    print(f"Error: {response.status_code}, {response.text}")
