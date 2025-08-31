import 'package:equatable/equatable.dart';

/// Sources 事件基类
abstract class SourcesEvent extends Equatable {
  const SourcesEvent();

  @override
  List<Object?> get props => [];
}

/// 加载来源事件
class LoadSources extends SourcesEvent {
  const LoadSources();
}

/// 刷新来源事件
class RefreshSources extends SourcesEvent {
  const RefreshSources();
}
