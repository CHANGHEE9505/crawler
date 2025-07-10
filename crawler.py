from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import csv
import os

# --- 설정 ---
SEARCH_KEYWORD = "종로3가역"
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV_NAME = "store_list_jongno.csv"
OUTPUT_CSV_PATH = os.path.join(DESKTOP_PATH, OUTPUT_CSV_NAME)
# ------------

url = 'https://map.kakao.com/'
driver = webdriver.Chrome()
driver.get(url)

print(f"'{SEARCH_KEYWORD}' 키워드로 검색을 시작합니다.")
try:
    search_area = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="search.keyword.query"]'
    )))
    search_area.send_keys(SEARCH_KEYWORD)
    driver.find_element(By.XPATH, '//*[@id="search.keyword.submit"]').send_keys(Keys.ENTER)
    time.sleep(2)

    # '장소' 탭 클릭
    place_tab = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//*[@id="info.main.options"]/li[2]/a'))
    )
    driver.execute_script("arguments[0].click();", place_tab)
    print("\n'장소' 탭을 클릭했습니다.")

except Exception as e:
    print(f"검색 또는 장소 탭 클릭 중 오류: {e}")
    driver.quit()
    exit()

def storeNamePrint(page):
    time.sleep(1) # 페이지가 완전히 그려질 시간을 줌
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    store_lists = soup.select('#info\\.search\\.place\\.list > li')
    data_list = []

    if not store_lists:
        print(f"{page}페이지에서 장소 정보를 찾을 수 없습니다.")
        return False

    print(f"--- {page}페이지 결과 수집 ---")
    for store in store_lists:
        try:
            name = store.select_one('.head_item > .tit_name > .link_name').text
            score_element = store.select_one('.rating > .score > .num')
            degree = score_element.text if score_element else "평점 없음"
            addr = ' '.join(store.select_one('.addr').text.split()) if store.select_one('.addr') else "주소 없음"
            tel = store.select_one('.contact > .phone').text if store.select_one('.contact') else "전화번호 없음"

            print(f"  - {name} (평점: {degree})")
            data_list.append([name, degree, addr, tel])
        except AttributeError:
            continue
    
    mode = 'w' if page == 1 else 'a'
    try:
        with open(OUTPUT_CSV_PATH, mode, encoding='utf-8-sig', newline='') as f:
            writercsv = csv.writer(f)
            if page == 1:
                header = ['name', 'degree', 'address', 'tel']
                writercsv.writerow(header)
            writercsv.writerows(data_list)
    except IOError as e:
        print(f"CSV 파일 저장 중 오류: {e}")
        return False
    return True

# --- 크롤링 실행 ---
try:
    if not storeNamePrint(1):
        raise Exception("첫 페이지에서 정보를 수집하지 못했습니다.")

    # '더보기' 버튼이 있으면 클릭
    try:
        more_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, 'info.search.place.more'))
        )
        driver.execute_script("arguments[0].click();", more_btn)
        print("\n'더보기' 버튼을 클릭했습니다.")
    except (NoSuchElementException, TimeoutException):
        print("\n'더보기' 버튼을 찾을 수 없거나 클릭할 수 없습니다.")

    # 2페이지부터 5페이지까지 정보 수집
    for i in range(2, 6):
        try:
            page_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, f'info.search.page.no{i}'))
            )
            driver.execute_script("arguments[0].click();", page_btn)
            if not storeNamePrint(i):
                break
        except (NoSuchElementException, TimeoutException):
            print(f"\n{i}페이지 버튼이 없어 수집을 중단합니다.")
            break

except Exception as e:
    print(f"\n크롤링 중 오류가 발생했습니다: {e}")

finally:
    print(f"\n**크롤링 완료**\n결과가 바탕화면의 '{OUTPUT_CSV_NAME}' 파일에 저장되었습니다.")
    driver.quit()