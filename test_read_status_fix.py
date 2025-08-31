#!/usr/bin/env python3
"""测试已读状态API修复

验证URL编码的post_id是否能正确处理
"""

import requests
import json
from urllib.parse import quote, unquote

# API 基础URL
BASE_URL = "http://localhost:8000/api/v1"

def test_read_status_api():
    """测试已读状态API"""
    print("=== 测试已读状态API修复 ===\n")
    
    # 测试用的URL post_id（模拟从数据库获取的URL）
    original_post_id = "http://blj.gxzf.gov.cn/"
    encoded_post_id = quote(original_post_id, safe='')
    
    print(f"原始 post_id: {original_post_id}")
    print(f"URL编码后: {encoded_post_id}")
    print(f"解码验证: {unquote(encoded_post_id)}")
    print()
    
    # 1. 首先获取文章列表，看看是否有数据
    print("1. 获取文章列表...")
    try:
        response = requests.get(f"{BASE_URL}/articles?page=1&limit=5")
        if response.status_code == 200:
            data = response.json()
            articles = data.get('data', [])
            print(f"   找到 {len(articles)} 篇文章")
            
            if articles:
                # 使用第一篇文章来测试
                first_article = articles[0]
                test_post_id = first_article['post_id']
                test_encoded_post_id = quote(test_post_id, safe='')
                
                print(f"   使用第一篇文章测试:")
                print(f"   post_id: {test_post_id}")
                print(f"   编码后: {test_encoded_post_id}")
                print()
                
                # 2. 测试切换已读状态
                print("2. 测试切换已读状态...")
                toggle_data = {"is_read": True}
                
                toggle_response = requests.put(
                    f"{BASE_URL}/articles/{test_encoded_post_id}/read-status",
                    json=toggle_data
                )
                
                print(f"   状态码: {toggle_response.status_code}")
                if toggle_response.status_code == 200:
                    result = toggle_response.json()
                    print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    print("   ✅ 切换已读状态成功!")
                else:
                    print(f"   ❌ 切换已读状态失败: {toggle_response.text}")
                print()
                
                # 3. 测试获取已读状态
                print("3. 测试获取已读状态...")
                status_response = requests.get(
                    f"{BASE_URL}/articles/{test_encoded_post_id}/read-status"
                )
                
                print(f"   状态码: {status_response.status_code}")
                if status_response.status_code == 200:
                    result = status_response.json()
                    print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    print("   ✅ 获取已读状态成功!")
                else:
                    print(f"   ❌ 获取已读状态失败: {status_response.text}")
                print()
                
                # 4. 测试获取文章详情
                print("4. 测试获取文章详情...")
                detail_response = requests.get(
                    f"{BASE_URL}/articles/{test_encoded_post_id}"
                )
                
                print(f"   状态码: {detail_response.status_code}")
                if detail_response.status_code == 200:
                    result = detail_response.json()
                    print(f"   文章标题: {result.get('title', 'N/A')}")
                    print("   ✅ 获取文章详情成功!")
                else:
                    print(f"   ❌ 获取文章详情失败: {detail_response.text}")
                print()
                
            else:
                print("   没有找到文章数据，无法进行测试")
                
        else:
            print(f"   ❌ 获取文章列表失败: {response.status_code} - {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 请求失败: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_read_status_api()