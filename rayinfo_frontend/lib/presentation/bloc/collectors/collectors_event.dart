import 'package:equatable/equatable.dart';

/// 采集器事件基类
abstract class CollectorsEvent extends Equatable {
  const CollectorsEvent();

  @override
  List<Object?> get props => [];
}

/// 加载采集器列表事件
class LoadCollectors extends CollectorsEvent {
  const LoadCollectors();
}

/// 刷新采集器列表事件
class RefreshCollectors extends CollectorsEvent {
  const RefreshCollectors();
}
