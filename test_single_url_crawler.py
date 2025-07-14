import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from selenium import webdriver
import time
import os
import csv
import re

sys.stdout.reconfigure(encoding='utf-8')

# --- 설정 ---
TARGET_URL = "https://place.map.kakao.com/967729291"
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV_NAME = "single_restaurant_test.csv"
OUTPUT_CSV_PATH = os.path.join(DESKTOP_PATH, OUTPUT_CSV_NAME)
# ------------

driver = None
try:
    driver = webdriver.Chrome()
    all_restaurants_data = []

    print(f"--- 단일 URL 상세 정보 크롤링 시작: {TARGET_URL} ---")

    try:
        print(f"  - {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.tit_place'))
        )
        html_detail = driver.page_source
        soup_detail = BeautifulSoup(html_detail, 'html.parser')

        store_name = soup_detail.select_one('h3.tit_place').text.replace('장소명', '').strip() if soup_detail.select_one('h3.tit_place') else "가게명 없음"
        store_image_element = soup_detail.select_one('div.board_photo img')
        store_image_url = store_image_element['src'] if store_image_element and 'src' in store_image_element.attrs else "이미지 없음"
        operating_hours = "영업시간 없음"
        try:
            expanded = False
            try:
                expand_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.ico_mapdesc.ico_arr16'))
                )
                driver.execute_script("arguments[0].click();", expand_button)
                time.sleep(2)
                html_after_expand = driver.page_source
                soup_detail = BeautifulSoup(html_after_expand, 'html.parser')
                expanded = True
            except (NoSuchElementException, TimeoutException):
                pass

            operation_info_section = soup_detail.select_one('div.default_info div.detail_info.info_operation')
            if operation_info_section:
                if expanded:
                    time_elements = operation_info_section.select('div.fold_detail div.line_fold')
                    if time_elements:
                        operating_hours_list = []
                        for line_fold in time_elements:
                            day_info = line_fold.select_one('span.tit_fold')
                            time_details = line_fold.select('div.detail_fold span.txt_detail')
                            if day_info and time_details:
                                times = [t.text.strip() for t in time_details]
                                operating_hours_list.append(f"{day_info.text.strip()} {' '.join(times)}")
                        operating_hours = "\n".join(operating_hours_list)
                else:
                    status_element = operation_info_section.select_one('span.tit_detail.emph_point2')
                    time_element = operation_info_section.select_one('span.txt_detail.add_mdot')
                    status = status_element.text.strip() if status_element else ""
                    time_info = time_element.text.strip() if time_element else ""
                    operating_hours = f"{status} {time_info}".strip()
        except Exception as e:
            print(f"    영업시간 추출 중 오류: {e}")
        menu_list = []
        try:
            more_menu_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.section_product div.wrap_more a.link_more'))
            )
            driver.execute_script("arguments[0].click();", more_menu_button)
            time.sleep(1)
            html_after_click = driver.page_source
            soup_after_click = BeautifulSoup(html_after_click, 'html.parser')
            menu_elements = soup_after_click.select('ul.list_goods li')
            for menu in menu_elements:
                name = menu.select_one('strong.tit_item').text.strip() if menu.select_one('strong.tit_item') else ""
                price = menu.select_one('p.desc_item').text.strip() if menu.select_one('p.desc_item') else ""
                menu_list.append(f"{name} ({price})")
        except (NoSuchElementException, TimeoutException):
            menu_elements = soup_detail.select('ul.list_goods li')
            for menu in menu_elements:
                name = menu.select_one('strong.tit_item').text.strip() if menu.select_one('strong.tit_item') else ""
                price = menu.select_one('p.desc_item').text.strip() if menu.select_one('p.desc_item') else ""
                menu_list.append(f"{name} ({price})")
        full_menu = ', '.join(menu_list) if menu_list else '메뉴 없음'
        score_element = soup_detail.select_one('span.starred_grade span.num_star')
        score = score_element.text.strip() if score_element else "평점 없음"
        parking_info = "주차 정보 없음"
        parking_element = soup_detail.select_one('div.unit_default.unit_infoetc h5.tit_addinfo:-soup-contains("주차") + div.detail_info span.txt_detail')
        if parking_element:
            parking_info = parking_element.text.strip()
        review_list = []
        try:
            review_tab = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul.list_tab li a[href="#comment"]'))
            )
            driver.execute_script("arguments[0].click();", review_tab)
            time.sleep(2)

            while True:
                try:
                    review_count_before_click = len(driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li'))
                    load_more_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.btn_more'))
                    )
                    driver.execute_script("arguments[0].click();", load_more_button)
                    WebDriverWait(driver, 5).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')) > review_count_before_click
                    )
                except (NoSuchElementException, TimeoutException):
                    break

            # --- 개별 리뷰 '내용 더보기' 클릭 ---
            # 모든 리뷰 엘리먼트를 가져와서 각각의 '더보기' 버튼을 클릭합니다.
            # StaleElementReferenceException을 피하기 위해 반복문 내에서 요소를 다시 찾습니다.
            while True:
                expanded_any_review_in_pass = False
                review_elements_for_expansion = driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')
                
                for review_idx in range(len(review_elements_for_expansion)):
                    try:
                        # Re-find the specific review element in each iteration to avoid staleness
                        current_review_element = driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')[review_idx]
                        
                        expand_button = current_review_element.find_element(By.CSS_SELECTOR, '.desc_review > a.link_more')
                        
                        # Only click if the button is visible and clickable
                        if expand_button.is_displayed() and expand_button.is_enabled():
                            driver.execute_script("arguments[0].click();", expand_button)
                            expanded_any_review_in_pass = True
                            time.sleep(0.5) # Wait for content to expand and DOM to update
                            # After clicking, the DOM might change, so we break and re-evaluate all reviews
                            break 
                    except NoSuchElementException:
                        # No '더보기' button for this review, move to the next
                        continue
                    except StaleElementReferenceException:
                        # If stale, treat as if something was expanded to re-enter loop
                        expanded_any_review_in_pass = True 
                        break
                    except Exception as e:
                        print(f"    개별 리뷰 '더보기' 클릭 중 오류: {e}")
                        # If other error, break the inner loop and re-evaluate
                        break
                
                if not expanded_any_review_in_pass:
                    break # No more expand buttons found or clicked in this pass, exit outer loop

            # --- 모든 리뷰 텍스트 추출 (확장된 내용 포함) ---
            # 모든 '더보기' 클릭이 완료된 후, 페이지 소스를 다시 가져와서 파싱합니다.
            html_after_expansions = driver.page_source
            soup_after_expansions = BeautifulSoup(html_after_expansions, 'html.parser')
            final_review_elements = soup_after_expansions.select('ul.list_review > li')

            for review_element in final_review_elements:
                try:
                    comment_element = review_element.select_one('.desc_review')
                    if comment_element:
                        full_comment = re.sub(r'\s+', ' ', comment_element.text).strip()
                        full_comment = re.sub(r'접기', '', full_comment).strip() # "접기" 텍스트 제거
                        review_list.append(full_comment)
                except Exception as e:
                    print(f"    최종 리뷰 텍스트 추출 중 오류: {e}")
                    continue

        except (NoSuchElementException, TimeoutException):
            pass
        all_reviews = '\n'.join(review_list) if review_list else '리뷰 없음'
        latitude = ""
        longitude = ""
        og_image_meta = soup_detail.find('meta', property='og:image')
        if og_image_meta and 'content' in og_image_meta.attrs:
            content = og_image_meta['content']
            match = re.search(r'm=([0-9.]+)\%2C([0-9.]+)', content)
            if match:
                longitude = match.group(1)
                latitude = match.group(2)
        address_element = soup_detail.select_one('div.unit_default h5.tit_info:-soup-contains("주소") + div.detail_info span.txt_detail')
        address = address_element.text.strip() if address_element else "주소 없음"

        data = {
            '구': "단일 테스트", # For single URL test, district is not relevant
            '가게명': store_name,
            '가게 이미지 URL': store_image_url,
            '영업시간': operating_hours,
            '전체 메뉴': full_menu,
            '평점': score,
            '주차 가능 여부': parking_info,
            '리뷰': all_reviews,
            '위도': latitude,
            '경도': longitude,
            '주소': address,
        }
        all_restaurants_data.append(data)

    except Exception as e:
        print(f"    상세 정보 추출 중 오류 발생: {TARGET_URL}, 오류: {e}")

    if all_restaurants_data:
        print("\n--- CSV 파일 저장 시작 ---")
        try:
            with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = all_restaurants_data[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_restaurants_data)
            print(f"\n**크롤링 완료**\n결과가 바탕화면의 '{OUTPUT_CSV_NAME}' 파일에 저장되었습니다.")
        except IOError as e:
            print(f"CSV 파일 저장 중 오류가 발생했습니다: {e}")
    else:
        print("\n추출된 식당 정보가 없습니다.")

finally:
    if driver:
        driver.quit()
        print("\n브라우저를 종료했습니다.")
