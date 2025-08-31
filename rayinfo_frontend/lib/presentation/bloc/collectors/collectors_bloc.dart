import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/repositories/collector_repository.dart';
import 'collectors_event.dart';
import 'collectors_state.dart';

/// 采集器Bloc
class CollectorsBloc extends Bloc<CollectorsEvent, CollectorsState> {
  final CollectorRepository _collectorRepository;

  CollectorsBloc({required CollectorRepository collectorRepository})
    : _collectorRepository = collectorRepository,
      super(const CollectorsInitial()) {
    on<LoadCollectors>(_onLoadCollectors);
    on<RefreshCollectors>(_onRefreshCollectors);
  }

  /// 处理加载采集器列表事件
  Future<void> _onLoadCollectors(
    LoadCollectors event,
    Emitter<CollectorsState> emit,
  ) async {
    emit(const CollectorsLoading());

    try {
      final collectorsResponse = await _collectorRepository.getCollectors();
      emit(CollectorsLoaded(collectorsResponse));
    } catch (error) {
      emit(CollectorsError(error.toString()));
    }
  }

  /// 处理刷新采集器列表事件
  Future<void> _onRefreshCollectors(
    RefreshCollectors event,
    Emitter<CollectorsState> emit,
  ) async {
    // 刷新时不显示loading状态，保持当前状态
    try {
      final collectorsResponse = await _collectorRepository.getCollectors();
      emit(CollectorsLoaded(collectorsResponse));
    } catch (error) {
      emit(CollectorsError(error.toString()));
    }
  }
}
