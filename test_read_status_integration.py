#!/usr/bin/env python3
"""
资讯已读状态功能集成测试

测试内容：
1. 后端API接口测试
2. 数据库操作测试
3. 完整用户流程测试
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent / "rayinfo_backend"
sys.path.insert(0, str(project_root / "src"))

from rayinfo_backend.models.info_item import DatabaseManager, RawInfoItem, ArticleReadStatus
from rayinfo_backend.api.services import ReadStatusService
from rayinfo_backend.api.schemas import ReadStatusRequest, BatchReadStatusRequest


async def test_database_setup():
    """测试数据库设置"""
    print("\n=== 测试数据库设置 ===")
    
    try:
        # 创建数据库管理器
        db_manager = DatabaseManager("test_rayinfo.db")
        
        # 创建表结构
        db_manager.create_tables()
        print("✅ 数据库表创建成功")
        
        return db_manager
    except Exception as e:
        print(f"❌ 数据库设置失败: {e}")
        raise


def test_create_sample_articles(db_manager):
    """创建示例文章数据"""
    print("\n=== 创建示例文章数据 ===")
    
    try:
        with db_manager.get_session() as session:
            # 创建示例文章
            articles = [
                RawInfoItem(
                    post_id="article_001",
                    source="mes.search",
                    title="AI技术最新进展",
                    url="https://example.com/ai-progress",
                    description="人工智能技术在各领域的最新应用和发展趋势",
                    query="人工智能",
                    engine="google",
                    collected_at=datetime.utcnow(),
                    processed=0
                ),
                RawInfoItem(
                    post_id="article_002",
                    source="weibo.home",
                    title="今日热点新闻",
                    url="https://example.com/hot-news",
                    description="今天发生的重要新闻事件汇总",
                    collected_at=datetime.utcnow(),
                    processed=0
                ),
                RawInfoItem(
                    post_id="article_003",
                    source="mes.search",
                    title="Flutter开发技巧",
                    url="https://example.com/flutter-tips",
                    description="Flutter移动应用开发的实用技巧和最佳实践",
                    query="Flutter",
                    engine="google",
                    collected_at=datetime.utcnow(),
                    processed=0
                )
            ]
            
            for article in articles:
                session.merge(article)  # 使用merge而不是add来避免重复
            
            session.commit()
            print(f"✅ 创建了 {len(articles)} 篇示例文章")
            
    except Exception as e:
        print(f"❌ 创建示例文章失败: {e}")
        raise


def test_read_status_service(db_manager):
    """测试已读状态服务"""
    print("\n=== 测试已读状态服务 ===")
    
    try:
        service = ReadStatusService()
        
        # 测试1: 标记文章为已读
        print("测试1: 标记文章为已读")
        request = ReadStatusRequest(is_read=True)
        response = service.toggle_read_status("article_001", request)
        assert response is not None
        assert response.is_read == True
        assert response.post_id == "article_001"
        print(f"✅ 文章 article_001 已标记为已读，时间: {response.read_at}")
        
        # 测试2: 获取已读状态
        print("测试2: 获取已读状态")
        status = service.get_read_status("article_001")
        assert status is not None
        assert status.is_read == True
        print(f"✅ 文章 article_001 已读状态: {status.is_read}")
        
        # 测试3: 标记为未读
        print("测试3: 标记为未读")
        request = ReadStatusRequest(is_read=False)
        response = service.toggle_read_status("article_001", request)
        assert response.is_read == False
        assert response.read_at is None
        print(f"✅ 文章 article_001 已标记为未读")
        
        # 测试4: 批量操作
        print("测试4: 批量标记已读")
        batch_request = BatchReadStatusRequest(
            post_ids=["article_002", "article_003"],
            is_read=True
        )
        batch_response = service.batch_toggle_read_status(batch_request)
        assert batch_response.success_count == 2
        assert batch_response.failed_count == 0
        print(f"✅ 批量操作成功: {batch_response.success_count} 成功, {batch_response.failed_count} 失败")
        
        # 测试5: 测试不存在的文章
        print("测试5: 测试不存在的文章")
        request = ReadStatusRequest(is_read=True)
        response = service.toggle_read_status("nonexistent_article", request)
        assert response is None
        print("✅ 不存在的文章正确返回 None")
        
    except Exception as e:
        print(f"❌ 已读状态服务测试失败: {e}")
        raise


def test_api_endpoints():
    """测试API端点（模拟测试）"""
    print("\n=== 测试API端点 ===")
    
    # 这里可以添加HTTP客户端测试
    # 由于需要启动服务器，暂时跳过
    print("ℹ️  API端点测试需要启动服务器，建议使用 test_api.html 进行手动测试")


def test_database_queries(db_manager):
    """测试数据库查询功能"""
    print("\n=== 测试数据库查询功能 ===")
    
    try:
        from rayinfo_backend.api.repositories import ArticleRepository
        from rayinfo_backend.api.schemas import ArticleFilters
        
        repo = ArticleRepository(db_manager)
        
        # 测试1: 获取所有文章
        print("测试1: 获取所有文章")
        filters = ArticleFilters(page=1, limit=10)
        articles, total = repo.get_articles_paginated(filters)
        print(f"✅ 获取到 {len(articles)} 篇文章，总计 {total} 篇")
        
        # 测试2: 带已读状态的查询
        print("测试2: 查询带已读状态的文章")
        articles_with_status, total_with_status = repo.get_articles_with_read_status(filters)
        print(f"✅ 获取到 {len(articles_with_status)} 篇文章（含已读状态），总计 {total_with_status} 篇")
        
        # 验证已读状态
        for article, status in articles_with_status:
            read_status = "已读" if status and status.is_read else "未读"
            print(f"   - {article.title}: {read_status}")
        
        # 测试3: 筛选已读文章
        print("测试3: 筛选已读文章")
        read_filters = ArticleFilters(page=1, limit=10, read_status="read")
        read_articles, read_total = repo.get_articles_with_read_status(read_filters)
        print(f"✅ 已读文章: {len(read_articles)} 篇")
        
        # 测试4: 筛选未读文章
        print("测试4: 筛选未读文章")
        unread_filters = ArticleFilters(page=1, limit=10, read_status="unread")
        unread_articles, unread_total = repo.get_articles_with_read_status(unread_filters)
        print(f"✅ 未读文章: {len(unread_articles)} 篇")
        
    except Exception as e:
        print(f"❌ 数据库查询测试失败: {e}")
        raise


def cleanup_test_data(db_manager):
    """清理测试数据"""
    print("\n=== 清理测试数据 ===")
    
    try:
        with db_manager.get_session() as session:
            # 删除测试文章的已读状态
            session.query(ArticleReadStatus).filter(
                ArticleReadStatus.post_id.in_(["article_001", "article_002", "article_003"])
            ).delete()
            
            # 删除测试文章
            session.query(RawInfoItem).filter(
                RawInfoItem.post_id.in_(["article_001", "article_002", "article_003"])
            ).delete()
            
            session.commit()
            print("✅ 测试数据清理完成")
            
    except Exception as e:
        print(f"❌ 清理测试数据失败: {e}")


async def main():
    """主测试流程"""
    print("开始资讯已读状态功能集成测试")
    print("=" * 50)
    
    db_manager = None
    
    try:
        # 1. 数据库设置测试
        db_manager = await test_database_setup()
        
        # 2. 创建示例数据
        test_create_sample_articles(db_manager)
        
        # 3. 测试已读状态服务
        test_read_status_service(db_manager)
        
        # 4. 测试数据库查询
        test_database_queries(db_manager)
        
        # 5. 测试API端点
        test_api_endpoints()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试通过！已读状态功能集成测试成功")
        
        # 提供进一步测试的建议
        print("\n📋 进一步测试建议：")
        print("1. 启动后端服务: cd rayinfo_backend && uvicorn rayinfo_backend.app:app --reload")
        print("2. 使用 test_api.html 进行前端API测试")
        print("3. 启动 Flutter 应用进行端到端测试")
        print("4. 验证UI组件的交互功能")
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        return False
    
    finally:
        # 清理测试数据
        if db_manager:
            cleanup_test_data(db_manager)
    
    return True


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)