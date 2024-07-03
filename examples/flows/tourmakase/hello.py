# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.core import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need

import datetime
import time
import requests
import urllib.parse

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    def get(self, endpoint):
        url = self.base_url + endpoint
        print('get', url)
        response = requests.get(url)
        return response.json()
    
    def post(self, endpoint, data):
        url = self.base_url + endpoint
        print('post', url, data)
        response = requests.post(url, json=data)
        return response.json()
    

@tool
def my_python_tool(travelStyle: str, arrival: str, departureDate: str, returnDate: str, adult:int, totalAmount:int):
    apiClient = APIClient("https://triple.guide/api")

    # arrival = 'TYO'
    # departureDate = '2024-10-15'
    # returnDate = '2024-10-22'
    # adult = 2
    # children = [1, 5]

    uri = "/air/intl/search/flights/search/CITY:SEL-CITY:" + str(arrival) + "/" + str(departureDate) + "/" + str(returnDate) \
        + "?cabins=ECONOMY&cabins=PREMIUM_ECONOMY" \
        + "&adult=" + str(adult) \
        + "&freeBaggageOnly=false"
    airInitResponse = apiClient.get(uri)

    listKey = airInitResponse['key']

    uri = "/city/search?page=0&size=40&keyword=" + str(arrival)
    cityResponse= apiClient.get(uri)

    cityRegionId = ''
    cityName = ''
    for result in cityResponse[0]['results']:
        if result['location']['type'] == 'CITY' and result['location']['iataCode'] == arrival:
            location = result['location']
            cityRegionId = location['regionId']
            cityName = location['names']['ko']
            break
            

    print(cityRegionId)

    uri = "/catalog/search?query=" +  urllib.parse.quote(cityName)
    catalogResponse = apiClient.get(uri)

    catalogId = catalogResponse['result'][0]['data'][0]['id']
    print(catalogId)

    uri = "/catalog/hotels?regionId=" + str(cityRegionId) \
        + "&categoryCityId=" + str(catalogId) \
        + "&checkIn=" + departureDate \
        + "&checkOut=" + returnDate \
        + "&numberOfAdults=" + str(adult) \
        + "&sort=default" \
        + "&benefitGroupFilter"

    hotelResponse = apiClient.get(uri)

    uri = "/catalog/tna/products?regionId=" + cityRegionId + "&from=0&size=100"
    tnaResponse = apiClient.get(uri)

    uri = "/air/intl/search/flights/" + listKey
    requestData =  {
        "size": 50,
        "sort": "RECOMMENDATION"
    }
    airResponse = apiClient.post(uri, requestData)

    while airResponse['status'] == 'PENDING':
        airResponse = apiClient.post(uri, requestData)
        print(airResponse['status'])
        time.sleep(1)

    # 날짜 문자열을 datetime 객체로 변환
    departure_date = datetime.datetime.strptime(departureDate, '%Y-%m-%d')
    return_date = datetime.datetime.strptime(returnDate, '%Y-%m-%d')

    # 날짜 차이 계산
    date_diff = return_date - departure_date
    days_diff_days = date_diff.days  # 차이가 몇 일인지 계산

    extracted_hotel_data = []
    for content in hotelResponse['data']:
        extracted_data = {
            "type": content['source']['type'],
            "reviewsRating": content['source']['reviewsRating'],
            "name": content['source']['names']['ko'] if 'ko' in content['source']['names'] else content['source']['names']['en'],
            "grade": content['source']['grade'],
            "starRating": content['source']['starRating'] if 'starRating' in content['source'] else 0,
            "price": content['priceInfos'][0]['display']['price'] * days_diff_days
        }
        extracted_hotel_data.append(extracted_data)

    extracted_tna_data = []
    for content in tnaResponse['data']:
        extracted_data = {
            "title": content['title'],
            "salePrice": content['salePrice'] * adult,
            # "areaName": content['areas'][0]['name'],  # 첫 번째 area의 name 필드
            # "regionName": content['regions'][0]['name'],  # 첫 번째 region의 name 필드
            "categoriesName": content['categories'][0]['name']  # 첫 번째 categories의 name 필드
        }
        extracted_tna_data.append(extracted_data)

    # 필요한 필드들을 추출하여 새로운 JSON 객체로 구성
    extracted_air_data = []
    for content in airResponse['contents']:
        extracted_data = {
            "totalPrice": content['totalPrice'],
            # "carrierCode_dep": content['schedules'][0]['carrier']['code'],  # 첫 번째 스케줄의 항공사 코드
            "carrierName_dep": content['schedules'][0]['carrier']['name'],  # 첫 번째 스케줄의 항공사 이름
            "dep_departure": content['schedules'][0]['departure'],  # 첫 번째 스케줄의 출발지
            "dep_arrival": content['schedules'][0]['arrival'],  # 첫 번째 스케줄의 도착지
            "dep_departureDateTime": content['schedules'][0]['departureDateTime'],  # 첫 번째 스케줄의 출발 일시
            "dep_arrivalDateTime": content['schedules'][0]['arrivalDateTime'],  # 첫 번째 스케줄의 도착 일시
            "dep_freeBaggageUnit": content['schedules'][0]['freeBaggage']['unit'],  # 첫 번째 스케줄의 수하물 단위
            # "carrierCode_arr": content['schedules'][1]['carrier']['code'],  # 두 번째 스케줄의 항공사 코드
            "carrierName_arr": content['schedules'][1]['carrier']['name'],  # 두 번째 스케줄의 항공사 이름
            "arr_departure": content['schedules'][1]['departure'],  # 두 번째 스케줄의 출발지
            "arr_arrival": content['schedules'][1]['arrival'],  # 두 번째 스케줄의 도착지
            "arr_departureDateTime": content['schedules'][1]['departureDateTime'],  # 두 번째 스케줄의 출발 일시
            "arr_arrivalDateTime": content['schedules'][1]['arrivalDateTime'],  # 두 번째 스케줄의 도착 일시
            "arr_freeBaggageUnit": content['schedules'][1]['freeBaggage']['unit'],  # 두 번째 스케줄의 수하물 단위
            "arr_freeBaggageAllowance": content['schedules'][1]['freeBaggage']['allowance']  # 두 번째 스케줄의 수하물 허용량
        }
        extracted_air_data.append(extracted_data)

    return {
        "omakaseData" : {
            "extracted_air_data" : extracted_air_data,
            "extracted_hotel_data" : extracted_hotel_data,
            "extracted_tna_data" : extracted_tna_data,
        },
        "total_person" : adult,
        "travelStyle" : travelStyle,
        "totalAmount" : totalAmount,
    }
