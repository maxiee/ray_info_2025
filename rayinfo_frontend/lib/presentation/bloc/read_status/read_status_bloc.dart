import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import '../../../domain/repositories/article_repository.dart';
import '../../../data/models/read_status_models.dart';
import 'read_status_event.dart';
import 'read_status_state.dart';

/// 已读状态BLoC
/// 
/// 管理资讯的已读状态操作，包括：
/// - 单个资讯的已读状态切换
/// - 批量已读状态操作
/// - 已读状态查询
/// - 错误处理和重试机制
class ReadStatusBloc extends Bloc<ReadStatusEvent, ReadStatusState> {
  final ArticleRepository _repository;

  ReadStatusBloc({
    required ArticleRepository repository,
  })  : _repository = repository,
        super(const ReadStatusInitial()) {
    
    // 注册事件处理器
    on<ToggleReadStatus>(_onToggleReadStatus);
    on<BatchToggleReadStatus>(_onBatchToggleReadStatus);
    on<GetReadStatus>(_onGetReadStatus);
    on<ResetReadStatus>(_onResetReadStatus);
  }

  /// 处理切换单个资讯已读状态事件
  Future<void> _onToggleReadStatus(
    ToggleReadStatus event,
    Emitter<ReadStatusState> emit,
  ) async {
    try {
      // 发出加载状态
      emit(ReadStatusLoading(postId: event.postId));

      // 调用仓库层方法
      final request = ReadStatusRequest(isRead: event.isRead);
      final response = await _repository.toggleReadStatus(event.postId, request);

      // 发出成功状态
      emit(ReadStatusSuccess(
        postId: response.postId,
        isRead: response.isRead,
        readAt: response.readAt,
        updatedAt: response.updatedAt,
      ));

    } on DioException catch (e) {
      // 网络错误处理
      _handleDioError(e, emit, event.postId);
    } catch (e) {
      // 其他错误处理
      emit(ReadStatusError(
        message: '切换已读状态失败: ${e.toString()}',
        postId: event.postId,
      ));
    }
  }

  /// 处理批量切换已读状态事件
  Future<void> _onBatchToggleReadStatus(
    BatchToggleReadStatus event,
    Emitter<ReadStatusState> emit,
  ) async {
    try {
      // 发出加载状态
      emit(const ReadStatusLoading());

      // 调用仓库层方法
      final request = BatchReadStatusRequest(
        postIds: event.postIds,
        isRead: event.isRead,
      );
      final response = await _repository.batchToggleReadStatus(request);

      // 发出成功状态
      emit(BatchReadStatusSuccess(
        successCount: response.successCount,
        failedCount: response.failedCount,
        results: response.results,
      ));

    } on DioException catch (e) {
      // 网络错误处理
      _handleDioError(e, emit, null);
    } catch (e) {
      // 其他错误处理
      emit(ReadStatusError(
        message: '批量切换已读状态失败: ${e.toString()}',
      ));
    }
  }

  /// 处理获取已读状态事件
  Future<void> _onGetReadStatus(
    GetReadStatus event,
    Emitter<ReadStatusState> emit,
  ) async {
    try {
      // 发出加载状态
      emit(ReadStatusLoading(postId: event.postId));

      // 调用仓库层方法
      final response = await _repository.getReadStatus(event.postId);

      // 发出成功状态
      emit(ReadStatusFetched(readStatus: response));

    } on DioException catch (e) {
      // 网络错误处理
      _handleDioError(e, emit, event.postId);
    } catch (e) {
      // 其他错误处理
      emit(ReadStatusError(
        message: '获取已读状态失败: ${e.toString()}',
        postId: event.postId,
      ));
    }
  }

  /// 处理重置状态事件
  void _onResetReadStatus(
    ResetReadStatus event,
    Emitter<ReadStatusState> emit,
  ) {
    emit(const ReadStatusInitial());
  }

  /// 处理Dio网络错误
  void _handleDioError(
    DioException error,
    Emitter<ReadStatusState> emit,
    String? postId,
  ) {
    String message;
    bool isNetworkError = false;

    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        message = '网络连接超时，请检查网络连接';
        isNetworkError = true;
        break;
      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        if (statusCode == 404) {
          message = '资讯不存在';
        } else if (statusCode == 500) {
          message = '服务器内部错误';
        } else {
          message = '服务器响应异常 (${statusCode ?? '未知'})';
        }
        break;
      case DioExceptionType.cancel:
        message = '请求已取消';
        break;
      case DioExceptionType.unknown:
      default:
        message = '网络连接失败，请检查网络设置';
        isNetworkError = true;
        break;
    }

    if (isNetworkError) {
      emit(ReadStatusNetworkError(message: message, postId: postId));
    } else {
      emit(ReadStatusError(message: message, postId: postId));
    }
  }

  /// 便捷方法：标记为已读
  void markAsRead(String postId) {
    add(ToggleReadStatus(postId: postId, isRead: true));
  }

  /// 便捷方法：标记为未读
  void markAsUnread(String postId) {
    add(ToggleReadStatus(postId: postId, isRead: false));
  }

  /// 便捷方法：批量标记为已读
  void batchMarkAsRead(List<String> postIds) {
    add(BatchToggleReadStatus(postIds: postIds, isRead: true));
  }

  /// 便捷方法：批量标记为未读
  void batchMarkAsUnread(List<String> postIds) {
    add(BatchToggleReadStatus(postIds: postIds, isRead: false));
  }
}