import 'package:equatable/equatable.dart';
import '../../../domain/entities/source.dart';

/// Sources 状态基类
abstract class SourcesState extends Equatable {
  const SourcesState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class SourcesInitial extends SourcesState {}

/// 加载中状态
class SourcesLoading extends SourcesState {}

/// 加载成功状态
class SourcesLoaded extends SourcesState {
  final List<Source> sources;

  const SourcesLoaded(this.sources);

  @override
  List<Object?> get props => [sources];
}

/// 加载失败状态
class SourcesError extends SourcesState {
  final String message;

  const SourcesError(this.message);

  @override
  List<Object?> get props => [message];
}
