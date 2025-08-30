import 'package:equatable/equatable.dart';

/// 分页信息模型
class Pagination extends Equatable {
  final int currentPage;
  final int totalPages;
  final int totalItems;
  final int perPage;
  final bool hasNext;
  final bool hasPrev;
  
  const Pagination({
    required this.currentPage,
    required this.totalPages,
    required this.totalItems,
    required this.perPage,
    required this.hasNext,
    required this.hasPrev,
  });
  
  /// 从 JSON 创建 Pagination 实例
  factory Pagination.fromJson(Map<String, dynamic> json) {
    return Pagination(
      currentPage: json['current_page'] as int,
      totalPages: json['total_pages'] as int,
      totalItems: json['total_items'] as int,
      perPage: json['per_page'] as int,
      hasNext: json['has_next'] as bool,
      hasPrev: json['has_prev'] as bool,
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'current_page': currentPage,
      'total_pages': totalPages,
      'total_items': totalItems,
      'per_page': perPage,
      'has_next': hasNext,
      'has_prev': hasPrev,
    };
  }
  
  @override
  List<Object?> get props => [
    currentPage,
    totalPages,
    totalItems,
    perPage,
    hasNext,
    hasPrev,
  ];
}