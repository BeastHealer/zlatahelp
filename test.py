import requests
import urllib3

# Отключение предупреждений о небезопасных SSL запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

payload = {
    'scope': 'GIGACHAT_API_PERS'
}
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
    'RqUID': '0199ce4a-456d-76aa-8848-06bffe4bf6fa',
    'Authorization': 'Basic MDE5OWNlNGEtNDU2ZC03NmFhLTg4NDgtMDZiZmZlNGJmNmZhOmVhY2MxNzZlLTY0NjUtNDA0OS04Mjc5LTMzNDhiNTAxMDhmMQ=='
}

# verify=False отключает проверку SSL сертификата
response = requests.post(url, headers=headers, data=payload, verify=False)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200:
    try:
        result = response.json()
        if 'access_token' in result:
            print(f"\n✅ Access Token получен успешно!")
            print(f"Access Token: {result['access_token'][:50]}...")
        else:
            print(f"\n❌ Access Token не найден в ответе")
    except Exception as e:
        print(f"\n❌ Ошибка при парсинге JSON: {e}")
else:
    print(f"\n❌ Ошибка: HTTP {response.status_code}")