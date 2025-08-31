import 'package:flutter/material.dart';
import '../../data/models/collector_models.dart';

/// 采集器实例列表组件
///
/// 显示特定采集器类型下的所有实例列表
/// 类似RSS阅读器的订阅源列表
class CollectorInstancesList extends StatelessWidget {
  final CollectorType? selectedCollectorType;
  final String? selectedInstanceId;
  final Function(CollectorInstance) onInstanceSelected;
  final VoidCallback? onRefresh;

  const CollectorInstancesList({
    super.key,
    this.selectedCollectorType,
    this.selectedInstanceId,
    required this.onInstanceSelected,
    this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: 300,
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(right: BorderSide(color: theme.dividerColor, width: 1)),
      ),
      child: Column(
        children: [
          // 头部区域
          _buildHeader(context),

          const Divider(height: 1),

          // 实例列表
          Expanded(child: _buildInstancesList(context)),
        ],
      ),
    );
  }

  /// 构建头部区域
  Widget _buildHeader(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          // 标题
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  selectedCollectorType?.displayName ?? '选择采集器',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.primary,
                  ),
                ),
                if (selectedCollectorType != null)
                  Text(
                    '${selectedCollectorType!.totalInstances} 个实例',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                  ),
              ],
            ),
          ),

          // 刷新按钮
          if (onRefresh != null)
            IconButton(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              iconSize: 20,
              tooltip: '刷新',
              style: IconButton.styleFrom(
                backgroundColor: theme.colorScheme.primary.withOpacity(0.1),
                foregroundColor: theme.colorScheme.primary,
              ),
            ),
        ],
      ),
    );
  }

  /// 构建实例列表
  Widget _buildInstancesList(BuildContext context) {
    if (selectedCollectorType == null) {
      return _buildEmptyState(context, '请在左侧选择一个采集器');
    }

    if (selectedCollectorType!.instances.isEmpty) {
      return _buildEmptyState(context, '该采集器暂无实例');
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: ListView.builder(
        itemCount: selectedCollectorType!.instances.length,
        itemBuilder: (context, index) {
          final instance = selectedCollectorType!.instances[index];
          return _buildInstanceItem(context, instance);
        },
      ),
    );
  }

  /// 构建空状态组件
  Widget _buildEmptyState(BuildContext context, String message) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.storage_outlined,
            size: 48,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.outline,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  /// 构建单个实例项
  Widget _buildInstanceItem(BuildContext context, CollectorInstance instance) {
    final theme = Theme.of(context);
    final isSelected = selectedInstanceId == instance.instanceId;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: InkWell(
        onTap: () => onInstanceSelected(instance),
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: isSelected
                ? theme.colorScheme.primaryContainer.withOpacity(0.5)
                : null,
            borderRadius: BorderRadius.circular(8),
            border: isSelected
                ? Border.all(
                    color: theme.colorScheme.primary.withOpacity(0.3),
                    width: 1,
                  )
                : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 实例名称和状态
              Row(
                children: [
                  // 状态指示器
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: _getStatusColor(instance.status, theme),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),

                  // 实例名称
                  Expanded(
                    child: Text(
                      instance.displayName,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: isSelected
                            ? theme.colorScheme.primary
                            : theme.colorScheme.onSurface,
                        fontWeight: isSelected
                            ? FontWeight.w600
                            : FontWeight.w400,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),

                  // 健康分数
                  _buildHealthScore(context, instance.healthScore),
                ],
              ),

              // 统计信息
              if (instance.runCount > 0 || instance.errorCount > 0)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: [
                      const SizedBox(width: 16), // 对齐状态指示器
                      // 运行次数
                      if (instance.runCount > 0) ...[
                        Icon(
                          Icons.play_circle_outline,
                          size: 12,
                          color: theme.colorScheme.outline,
                        ),
                        const SizedBox(width: 2),
                        Text(
                          '${instance.runCount}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.outline,
                          ),
                        ),
                      ],

                      // 错误次数
                      if (instance.errorCount > 0) ...[
                        const SizedBox(width: 8),
                        Icon(
                          Icons.error_outline,
                          size: 12,
                          color: theme.colorScheme.error,
                        ),
                        const SizedBox(width: 2),
                        Text(
                          '${instance.errorCount}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.error,
                          ),
                        ),
                      ],

                      // 最后运行时间
                      if (instance.lastRun != null) ...[
                        const Spacer(),
                        Text(
                          _formatLastRun(instance.lastRun!),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.outline,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  /// 构建健康分数组件
  Widget _buildHealthScore(BuildContext context, double healthScore) {
    final theme = Theme.of(context);
    final color = healthScore >= 0.8
        ? Colors.green
        : healthScore >= 0.5
        ? Colors.orange
        : Colors.red;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '${(healthScore * 100).toInt()}%',
        style: theme.textTheme.bodySmall?.copyWith(
          color: color,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  /// 获取状态对应的颜色
  Color _getStatusColor(String status, ThemeData theme) {
    switch (status.toLowerCase()) {
      case 'active':
        return Colors.green;
      case 'error':
        return Colors.red;
      case 'inactive':
        return Colors.grey;
      case 'expired':
        return Colors.orange;
      default:
        return theme.colorScheme.outline;
    }
  }

  /// 格式化最后运行时间
  String _formatLastRun(DateTime lastRun) {
    final now = DateTime.now();
    final difference = now.difference(lastRun);

    if (difference.inMinutes < 1) {
      return '刚刚';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}分钟前';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}小时前';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}天前';
    } else {
      return '${lastRun.month}/${lastRun.day}';
    }
  }
}
