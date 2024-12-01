import requests
import json

def get_dolly_response(system_content, user_content):
    # Define the API endpoint and headers
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer xai-da7pVmPJ5frkiun08Z9gW2uLuxvm7Dyt15ieESbJoN82xk4SudhwermLUkO9YxuY02J6U4vW0pOR2ylL"
    }

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
            return message
        else:
            return "No message found in the response."
    else:
        return f"Error: {response.status_code}, {response.text}"
