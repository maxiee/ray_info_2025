/// 应用程序核心常量
class AppConstants {
  // API 配置
  static const String baseUrl = 'http://localhost:8000';
  static const String apiVersion = '/api/v1';
  static const String apiBaseUrl = '$baseUrl$apiVersion';
  
  // 网络配置
  static const int connectTimeout = 30000; // 30秒
  static const int receiveTimeout = 30000; // 30秒
  static const int sendTimeout = 30000; // 30秒
  
  // 分页配置
  static const int defaultPageSize = 20;
  static const int maxPageSize = 100;
  
  // 缓存配置
  static const String cacheBoxName = 'rayinfo_cache';
  static const Duration cacheExpiration = Duration(hours: 1);
  
  // 应用信息
  static const String appName = 'RayInfo';
  static const String appDescription = '对抗算法投喂，夺回注意力主权';
}