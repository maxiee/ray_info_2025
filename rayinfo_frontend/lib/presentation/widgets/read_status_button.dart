import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/article.dart';
import '../bloc/read_status/read_status_bloc.dart';
import '../bloc/read_status/read_status_event.dart';
import '../bloc/read_status/read_status_state.dart';

/// 已读状态切换按钮组件
/// 
/// 支持以下功能：
/// - 显示当前已读/未读状态
/// - 点击切换已读状态
/// - 加载状态指示
/// - 错误状态处理
/// - 防抖动保护
class ReadStatusButton extends StatefulWidget {
  final Article article;
  final VoidCallback? onStatusChanged; // 状态变化回调
  final EdgeInsetsGeometry? padding;
  final double? iconSize;
  final Color? readColor; // 已读状态颜色
  final Color? unreadColor; // 未读状态颜色

  const ReadStatusButton({
    super.key,
    required this.article,
    this.onStatusChanged,
    this.padding,
    this.iconSize = 20.0,
    this.readColor,
    this.unreadColor,
  });

  @override
  State<ReadStatusButton> createState() => _ReadStatusButtonState();
}

class _ReadStatusButtonState extends State<ReadStatusButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;
  bool _isLoading = false;
  String? _lastProcessedPostId; // 防止重复处理

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 150),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: 0.9,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<ReadStatusBloc, ReadStatusState>(
      listener: _handleStateChange,
      child: BlocBuilder<ReadStatusBloc, ReadStatusState>(
        builder: (context, state) {
          // 检查是否正在处理当前资讯
          final isCurrentArticleLoading = state is ReadStatusLoading &&
              state.postId == widget.article.postId;

          return AnimatedBuilder(
            animation: _scaleAnimation,
            builder: (context, child) {
              return Transform.scale(
                scale: _scaleAnimation.value,
                child: _buildButton(context, isCurrentArticleLoading),
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildButton(BuildContext context, bool isLoading) {
    final theme = Theme.of(context);
    final isRead = widget.article.isRead;
    
    // 确定颜色
    final readColor = widget.readColor ?? theme.colorScheme.primary;
    final unreadColor = widget.unreadColor ?? theme.colorScheme.outline;
    final currentColor = isRead ? readColor : unreadColor;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: isLoading ? null : _handleTap,
        onTapDown: isLoading ? null : (_) => _animationController.forward(),
        onTapUp: isLoading ? null : (_) => _animationController.reverse(),
        onTapCancel: isLoading ? null : () => _animationController.reverse(),
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: widget.padding ?? const EdgeInsets.all(8.0),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // 图标或加载指示器
              if (isLoading)
                SizedBox(
                  width: widget.iconSize!,
                  height: widget.iconSize!,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.0,
                    valueColor: AlwaysStoppedAnimation<Color>(currentColor),
                  ),
                )
              else
                Icon(
                  isRead ? Icons.visibility : Icons.visibility_outlined,
                  size: widget.iconSize,
                  color: currentColor,
                ),
              
              const SizedBox(width: 4),
              
              // 文本标签
              Text(
                isRead ? '已读' : '标记已读',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: currentColor,
                  fontWeight: isRead ? FontWeight.w500 : FontWeight.w400,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _handleTap() {
    if (_isLoading) return;

    // 防抖动保护
    if (_lastProcessedPostId == widget.article.postId) {
      return;
    }

    _lastProcessedPostId = widget.article.postId;

    // 触发状态切换
    final newReadStatus = !widget.article.isRead;
    context.read<ReadStatusBloc>().add(
      ToggleReadStatus(
        postId: widget.article.postId,
        isRead: newReadStatus,
      ),
    );

    // 触觉反馈
    _provideFeedback();
  }

  void _handleStateChange(BuildContext context, ReadStatusState state) {
    // 只处理与当前资讯相关的状态变化
    final isCurrentArticle = _isCurrentArticleState(state);

    if (!isCurrentArticle) return;

    setState(() {
      _isLoading = state is ReadStatusLoading;
    });

    if (state is ReadStatusSuccess) {
      // 成功时清除防抖保护并触发回调
      _lastProcessedPostId = null;
      widget.onStatusChanged?.call();
      _showSuccessAnimation();
    } else if (state is ReadStatusError) {
      // 错误时清除防抖保护并显示错误信息
      _lastProcessedPostId = null;
      _showErrorMessage(context, state.message);
    } else if (state is ReadStatusNetworkError) {
      // 网络错误时清除防抖保护并显示网络错误
      _lastProcessedPostId = null;
      _showNetworkErrorMessage(context, state.message);
    }
  }

  bool _isCurrentArticleState(ReadStatusState state) {
    if (state is ReadStatusLoading) {
      return state.postId == widget.article.postId;
    } else if (state is ReadStatusSuccess) {
      return state.postId == widget.article.postId;
    } else if (state is ReadStatusError) {
      return state.postId == widget.article.postId;
    } else if (state is ReadStatusNetworkError) {
      return state.postId == widget.article.postId;
    }
    return false;
  }

  void _provideFeedback() {
    // 触觉反馈
    // HapticFeedback.lightImpact(); // 可以根据需要启用
  }

  void _showSuccessAnimation() {
    // 成功动画 - 可以添加更多视觉反馈
    _animationController.forward().then((_) {
      _animationController.reverse();
    });
  }

  void _showErrorMessage(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Theme.of(context).colorScheme.error,
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: '重试',
          textColor: Colors.white,
          onPressed: () => _handleTap(),
        ),
      ),
    );
  }

  void _showNetworkErrorMessage(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.wifi_off, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.orange,
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: '重试',
          textColor: Colors.white,
          onPressed: () => _handleTap(),
        ),
      ),
    );
  }
}

/// 简化版的已读状态切换按钮
/// 适用于空间有限的场景
class CompactReadStatusButton extends StatelessWidget {
  final Article article;
  final VoidCallback? onStatusChanged;

  const CompactReadStatusButton({
    super.key,
    required this.article,
    this.onStatusChanged,
  });

  @override
  Widget build(BuildContext context) {
    return ReadStatusButton(
      article: article,
      onStatusChanged: onStatusChanged,
      padding: const EdgeInsets.all(4.0),
      iconSize: 16.0,
    );
  }
}