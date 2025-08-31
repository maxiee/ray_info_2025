import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../domain/entities/article.dart';
import '../bloc/articles/articles_bloc.dart';
import 'read_status_button.dart';

/// 资讯卡片组件
class ArticleCard extends StatelessWidget {
  final Article article;
  final VoidCallback? onTap;
  
  const ArticleCard({
    Key? key,
    required this.article,
    this.onTap,
  }) : super(key: key);
  
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: InkWell(
        onTap: onTap ?? () => _launchUrl(article.url),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 标题
              if (article.title != null) ...[
                Text(
                  article.title!,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    height: 1.3,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 8),
              ],
              
              // 描述
              if (article.shortDescription != null) ...[
                Text(
                  article.shortDescription!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).textTheme.bodySmall?.color,
                    height: 1.4,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 12),
              ],
              
              // 底部信息栏
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // 来源标签
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      article.sourceDisplayName,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  
                  const SizedBox(width: 8),
                  
                  // 查询关键词（如果有）
                  if (article.query != null) ...[
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.secondary.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        article.query!,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.secondary,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  
                  const Spacer(),
                  
                  // 时间
                  Text(
                    article.relativeTime,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                  
                  // 外部链接图标
                  if (article.url != null) ...[
                    const SizedBox(width: 8),
                    Icon(
                      Icons.open_in_new,
                      size: 16,
                      color: Theme.of(context).textTheme.labelSmall?.color,
                    ),
                  ],
                ],
              ),
              
              const SizedBox(height: 8),
              
              // 已读状态按钮行
              Row(
                children: [
                  ReadStatusButton(
                    article: article,
                    onStatusChanged: () => _onReadStatusChanged(context),
                  ),
                  const Spacer(),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  /// 启动URL
  Future<void> _launchUrl(String? url) async {
    if (url == null || url.isEmpty) return;
    
    try {
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      debugPrint('启动URL失败: $e');
    }
  }
  
  /// 已读状态变化回调
  void _onReadStatusChanged(BuildContext context) {
    // 通知ArticlesBloc更新列表中的文章状态
    context.read<ArticlesBloc>().updateArticleStatus(
      article.postId,
      !article.isRead, // 切换状态
      !article.isRead ? DateTime.now() : null,
    );
  }
}