import 'package:http/http.dart' as http;
import 'dart:convert';

void main() async {
  await testReadStatusAPI();
}

Future<void> testReadStatusAPI() async {
  print('=== Flutter 已读状态API测试 ===\n');
  
  const baseUrl = 'http://localhost:8000/api/v1';
  
  try {
    // 1. 获取文章列表
    print('1. 获取文章列表...');
    final articlesResponse = await http.get(
      Uri.parse('$baseUrl/articles?page=1&limit=5'),
    );
    
    if (articlesResponse.statusCode == 200) {
      final articlesData = json.decode(articlesResponse.body);
      final articles = articlesData['data'] as List;
      print('   找到 ${articles.length} 篇文章');
      
      if (articles.isNotEmpty) {
        final firstArticle = articles[0];
        final postId = firstArticle['post_id'] as String;
        final encodedPostId = Uri.encodeComponent(postId);
        
        print('   测试文章: $postId');
        print('   编码后: $encodedPostId');
        print();
        
        // 2. 测试切换已读状态
        print('2. 测试切换已读状态...');
        final toggleResponse = await http.put(
          Uri.parse('$baseUrl/articles/$encodedPostId/read-status'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({'is_read': true}),
        );
        
        print('   状态码: ${toggleResponse.statusCode}');
        if (toggleResponse.statusCode == 200) {
          final result = json.decode(toggleResponse.body);
          print('   ✅ 切换已读状态成功!');
          print('   已读状态: ${result['is_read']}');
        } else {
          print('   ❌ 切换已读状态失败: ${toggleResponse.body}');
        }
        print();
        
        // 3. 测试获取已读状态
        print('3. 测试获取已读状态...');
        final statusResponse = await http.get(
          Uri.parse('$baseUrl/articles/$encodedPostId/read-status'),
        );
        
        print('   状态码: ${statusResponse.statusCode}');
        if (statusResponse.statusCode == 200) {
          final result = json.decode(statusResponse.body);
          print('   ✅ 获取已读状态成功!');
          print('   已读状态: ${result['is_read']}');
        } else {
          print('   ❌ 获取已读状态失败: ${statusResponse.body}');
        }
        print();
      }
    } else {
      print('   ❌ 获取文章列表失败: ${articlesResponse.statusCode}');
    }
    
  } catch (e) {
    print('❌ 测试过程中发生错误: $e');
  }
  
  print('\n=== 测试完成 ===');
}