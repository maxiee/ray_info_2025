import 'package:flutter_bloc/flutter_bloc.dart';
import 'sources_event.dart';
import 'sources_state.dart';
import '../../../domain/usecases/get_sources.dart';

/// Sources Bloc - 管理来源相关状态
class SourcesBloc extends Bloc<SourcesEvent, SourcesState> {
  final GetSourcesUseCase _getSourcesUseCase;

  SourcesBloc({required GetSourcesUseCase getSourcesUseCase})
    : _getSourcesUseCase = getSourcesUseCase,
      super(SourcesInitial()) {
    on<LoadSources>(_onLoadSources);
    on<RefreshSources>(_onRefreshSources);
  }

  /// 处理加载来源事件
  Future<void> _onLoadSources(
    LoadSources event,
    Emitter<SourcesState> emit,
  ) async {
    emit(SourcesLoading());

    try {
      final sources = await _getSourcesUseCase();
      emit(SourcesLoaded(sources));
    } catch (e) {
      emit(SourcesError('获取来源列表失败: ${e.toString()}'));
    }
  }

  /// 处理刷新来源事件
  Future<void> _onRefreshSources(
    RefreshSources event,
    Emitter<SourcesState> emit,
  ) async {
    // 刷新时不显示loading状态，保持当前状态
    try {
      final sources = await _getSourcesUseCase();
      emit(SourcesLoaded(sources));
    } catch (e) {
      emit(SourcesError('刷新来源列表失败: ${e.toString()}'));
    }
  }
}
