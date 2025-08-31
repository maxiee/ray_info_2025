import 'package:dio/dio.dart';
import '../constants/app_constants.dart';

/// HTTP客户端配置
class ApiClient {
  late final Dio _dio;
  
  ApiClient() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConstants.apiBaseUrl,
      connectTimeout: Duration(milliseconds: AppConstants.connectTimeout),
      receiveTimeout: Duration(milliseconds: AppConstants.receiveTimeout),
      sendTimeout: Duration(milliseconds: AppConstants.sendTimeout),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));
    
    // 添加拦截器
    _addInterceptors();
  }
  
  void _addInterceptors() {
    // 请求拦截器
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        // 可以在这里添加认证 token 等
        print('请求: ${options.method} ${options.path}');
        handler.next(options);
      },
      onResponse: (response, handler) {
        print('响应: ${response.statusCode} ${response.requestOptions.path}');
        handler.next(response);
      },
      onError: (error, handler) {
        print('错误: ${error.response?.statusCode} ${error.message}');
        handler.next(error);
      },
    ));
  }
  
  /// GET 请求
  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.get<T>(
        path,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }
  
  /// POST 请求
  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.post<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }
  
  /// PUT 请求
  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.put<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }
  
  /// 处理错误
  Exception _handleError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const NetworkException('网络连接超时，请检查网络连接');
      
      case DioExceptionType.badResponse:
        switch (error.response?.statusCode) {
          case 400:
            return const ApiException('请求参数错误');
          case 401:
            return const ApiException('未授权访问');
          case 403:
            return const ApiException('禁止访问');
          case 404:
            return const ApiException('请求的资源不存在');
          case 500:
            return const ApiException('服务器内部错误');
          default:
            return ApiException('请求失败：${error.response?.statusCode}');
        }
      
      case DioExceptionType.cancel:
        return const NetworkException('请求已取消');
      
      case DioExceptionType.unknown:
      default:
        return const NetworkException('网络连接失败，请检查网络连接');
    }
  }
}

/// 网络异常
class NetworkException implements Exception {
  final String message;
  const NetworkException(this.message);
  
  @override
  String toString() => 'NetworkException: $message';
}

/// API异常
class ApiException implements Exception {
  final String message;
  const ApiException(this.message);
  
  @override
  String toString() => 'ApiException: $message';
}