import 'package:flutter/material.dart';
import '../../data/models/read_status_models.dart';

/// 资讯筛选器组件
/// 
/// 支持以下筛选功能：
/// - 已读状态筛选（全部/未读/已读）
/// - 来源筛选
/// - 未来可扩展：时间范围筛选、关键词筛选等
class ArticleFilterBar extends StatefulWidget {
  final ReadStatusFilter selectedReadStatus;
  final String? selectedSource;
  final List<String> availableSources;
  final Function(ReadStatusFilter) onReadStatusChanged;
  final Function(String?) onSourceChanged;
  final VoidCallback? onClearFilters;
  final bool showClearButton;

  const ArticleFilterBar({
    super.key,
    required this.selectedReadStatus,
    required this.onReadStatusChanged,
    this.selectedSource,
    this.availableSources = const [],
    required this.onSourceChanged,
    this.onClearFilters,
    this.showClearButton = true,
  });

  @override
  State<ArticleFilterBar> createState() => _ArticleFilterBarState();
}

class _ArticleFilterBarState extends State<ArticleFilterBar>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _slideAnimation;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _slideAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(16.0),
      child: Column(
        children: [
          _buildMainFilterRow(context),
          AnimatedBuilder(
            animation: _slideAnimation,
            builder: (context, child) {
              return SizeTransition(
                sizeFactor: _slideAnimation,
                child: child,
              );
            },
            child: _buildExpandedFilters(context),
          ),
        ],
      ),
    );
  }

  Widget _buildMainFilterRow(BuildContext context) {
    final theme = Theme.of(context);
    
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Row(
        children: [
          // 已读状态筛选标签
          Icon(
            Icons.filter_list,
            size: 20,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Text(
            '筛选',
            style: theme.textTheme.titleSmall?.copyWith(
              color: theme.colorScheme.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 16),
          
          // 已读状态快速筛选按钮
          Expanded(
            child: _buildReadStatusFilters(context),
          ),
          
          // 展开/收起按钮
          if (widget.availableSources.isNotEmpty) ...[
            const SizedBox(width: 8),
            IconButton(
              onPressed: _toggleExpanded,
              icon: AnimatedRotation(
                turns: _isExpanded ? 0.5 : 0,
                duration: const Duration(milliseconds: 300),
                child: const Icon(Icons.expand_more),
              ),
              tooltip: _isExpanded ? '收起更多筛选' : '展开更多筛选',
            ),
          ],
          
          // 清除筛选按钮
          if (widget.showClearButton && _hasActiveFilters()) ...[
            const SizedBox(width: 8),
            TextButton.icon(
              onPressed: widget.onClearFilters,
              icon: const Icon(Icons.clear, size: 16),
              label: const Text('清除'),
              style: TextButton.styleFrom(
                foregroundColor: theme.colorScheme.outline,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildReadStatusFilters(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _buildReadStatusChip(
            context,
            ReadStatusFilter.all,
            '全部',
            Icons.list,
          ),
          const SizedBox(width: 8),
          _buildReadStatusChip(
            context,
            ReadStatusFilter.unread,
            '未读',
            Icons.visibility_outlined,
          ),
          const SizedBox(width: 8),
          _buildReadStatusChip(
            context,
            ReadStatusFilter.read,
            '已读',
            Icons.visibility,
          ),
        ],
      ),
    );
  }

  Widget _buildReadStatusChip(
    BuildContext context,
    ReadStatusFilter filter,
    String label,
    IconData icon,
  ) {
    final theme = Theme.of(context);
    final isSelected = widget.selectedReadStatus == filter;
    
    return FilterChip(
      selected: isSelected,
      onSelected: (_) => widget.onReadStatusChanged(filter),
      avatar: Icon(
        icon,
        size: 16,
        color: isSelected 
            ? theme.colorScheme.onPrimary 
            : theme.colorScheme.primary,
      ),
      label: Text(label),
      selectedColor: theme.colorScheme.primary,
      checkmarkColor: theme.colorScheme.onPrimary,
      labelStyle: TextStyle(
        color: isSelected 
            ? theme.colorScheme.onPrimary 
            : theme.colorScheme.onSurface,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
      ),
    );
  }

  Widget _buildExpandedFilters(BuildContext context) {
    if (!_isExpanded || widget.availableSources.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Divider(),
          const SizedBox(height: 8),
          
          // 来源筛选
          _buildSourceFilter(context),
        ],
      ),
    );
  }

  Widget _buildSourceFilter(BuildContext context) {
    final theme = Theme.of(context);
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.source,
              size: 16,
              color: theme.colorScheme.outline,
            ),
            const SizedBox(width: 8),
            Text(
              '信息来源',
              style: theme.textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            // 全部来源选项
            _buildSourceChip(context, null, '全部来源'),
            
            // 各个来源选项
            ...widget.availableSources.map(
              (source) => _buildSourceChip(context, source, _getSourceDisplayName(source)),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSourceChip(BuildContext context, String? source, String label) {
    final theme = Theme.of(context);
    final isSelected = widget.selectedSource == source;
    
    return FilterChip(
      selected: isSelected,
      onSelected: (_) => widget.onSourceChanged(source),
      label: Text(label),
      selectedColor: theme.colorScheme.secondaryContainer,
      checkmarkColor: theme.colorScheme.onSecondaryContainer,
      labelStyle: TextStyle(
        color: isSelected 
            ? theme.colorScheme.onSecondaryContainer 
            : theme.colorScheme.onSurface,
        fontWeight: isSelected ? FontWeight.w500 : FontWeight.w400,
      ),
    );
  }

  void _toggleExpanded() {
    setState(() {
      _isExpanded = !_isExpanded;
    });
    
    if (_isExpanded) {
      _animationController.forward();
    } else {
      _animationController.reverse();
    }
  }

  bool _hasActiveFilters() {
    return widget.selectedReadStatus != ReadStatusFilter.all ||
           widget.selectedSource != null;
  }

  String _getSourceDisplayName(String source) {
    const sourceNames = {
      'mes.search': '搜索引擎',
      'weibo.home': '微博首页',
      'rss.feed': 'RSS订阅',
    };
    return sourceNames[source] ?? source;
  }
}

/// 简化版筛选器 - 仅包含已读状态筛选
class SimpleReadStatusFilter extends StatelessWidget {
  final ReadStatusFilter selectedReadStatus;
  final Function(ReadStatusFilter) onReadStatusChanged;

  const SimpleReadStatusFilter({
    super.key,
    required this.selectedReadStatus,
    required this.onReadStatusChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      child: Row(
        children: [
          Text(
            '显示：',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(width: 12),
          
          // 已读状态选择器
          SegmentedButton<ReadStatusFilter>(
            segments: const [
              ButtonSegment(
                value: ReadStatusFilter.all,
                label: Text('全部'),
                icon: Icon(Icons.list, size: 16),
              ),
              ButtonSegment(
                value: ReadStatusFilter.unread,
                label: Text('未读'),
                icon: Icon(Icons.visibility_outlined, size: 16),
              ),
              ButtonSegment(
                value: ReadStatusFilter.read,
                label: Text('已读'),
                icon: Icon(Icons.visibility, size: 16),
              ),
            ],
            selected: {selectedReadStatus},
            onSelectionChanged: (selection) {
              if (selection.isNotEmpty) {
                onReadStatusChanged(selection.first);
              }
            },
            showSelectedIcon: false,
            style: SegmentedButton.styleFrom(
              visualDensity: VisualDensity.compact,
            ),
          ),
        ],
      ),
    );
  }
}

/// 筛选器状态数据类
class FilterState {
  final ReadStatusFilter readStatus;
  final String? source;
  final DateTime? startDate;
  final DateTime? endDate;

  const FilterState({
    this.readStatus = ReadStatusFilter.all,
    this.source,
    this.startDate,
    this.endDate,
  });

  FilterState copyWith({
    ReadStatusFilter? readStatus,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  }) {
    return FilterState(
      readStatus: readStatus ?? this.readStatus,
      source: source ?? this.source,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
    );
  }

  bool get hasActiveFilters {
    return readStatus != ReadStatusFilter.all ||
           source != null ||
           startDate != null ||
           endDate != null;
  }

  FilterState get cleared {
    return const FilterState();
  }
}