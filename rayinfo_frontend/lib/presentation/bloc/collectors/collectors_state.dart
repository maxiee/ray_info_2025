import 'package:equatable/equatable.dart';
import '../../../data/models/collector_models.dart';

/// 采集器状态基类
abstract class CollectorsState extends Equatable {
  const CollectorsState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class CollectorsInitial extends CollectorsState {
  const CollectorsInitial();
}

/// 加载中状态
class CollectorsLoading extends CollectorsState {
  const CollectorsLoading();
}

/// 加载成功状态
class CollectorsLoaded extends CollectorsState {
  final CollectorsResponse collectorsResponse;

  const CollectorsLoaded(this.collectorsResponse);

  @override
  List<Object?> get props => [collectorsResponse];

  /// 获取采集器类型列表
  List<CollectorType> get collectorTypes => collectorsResponse.collectorTypes;
}

/// 加载失败状态
class CollectorsError extends CollectorsState {
  final String message;

  const CollectorsError(this.message);

  @override
  List<Object?> get props => [message];
}
