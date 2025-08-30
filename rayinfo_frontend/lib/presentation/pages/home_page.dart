import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/articles/articles_bloc.dart';
import '../bloc/articles/articles_event.dart';
import '../bloc/articles/articles_state.dart';
import '../widgets/article_card.dart';

/// 首页 - 资讯列表
class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);
  
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final ScrollController _scrollController = ScrollController();
  
  @override
  void initState() {
    super.initState();
    
    // 初始加载数据
    context.read<ArticlesBloc>().add(const LoadArticles());
    
    // 设置滚动监听，实现无限滚动
    _scrollController.addListener(() {
      if (_scrollController.position.pixels >= 
          _scrollController.position.maxScrollExtent - 200) {
        // 距离底部200像素时开始加载更多
        context.read<ArticlesBloc>().add(const LoadMoreArticles());
      }
    });
  }
  
  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('RayInfo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: 导航到搜索页面
              Navigator.pushNamed(context, '/search');
            },
          ),
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: () {
              // TODO: 显示筛选对话框
              _showFilterDialog();
            },
          ),
        ],
      ),
      body: BlocBuilder<ArticlesBloc, ArticlesState>(
        builder: (context, state) {
          return RefreshIndicator(
            onRefresh: () async {
              context.read<ArticlesBloc>().add(const RefreshArticles());
            },
            child: _buildBody(state),
          );
        },
      ),
    );
  }
  
  Widget _buildBody(ArticlesState state) {
    if (state is ArticlesLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    
    if (state is ArticlesError) {
      return _buildErrorWidget(state.message);
    }
    
    if (state is ArticlesLoaded) {
      return _buildArticlesList(state);
    }
    
    return const Center(child: Text('暂无数据'));
  }
  
  Widget _buildErrorWidget(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 16),
          Text(
            '加载失败',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () {
              context.read<ArticlesBloc>().add(const LoadArticles());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }
  
  Widget _buildArticlesList(ArticlesLoaded state) {
    if (state.articles.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.article_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('暂无资讯', style: TextStyle(fontSize: 18, color: Colors.grey)),
          ],
        ),
      );
    }
    
    return ListView.builder(
      controller: _scrollController,
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: state.articles.length + (state.isLoadingMore ? 1 : 0),
      itemBuilder: (context, index) {
        // 显示加载更多指示器
        if (index == state.articles.length) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        
        final article = state.articles[index];
        return ArticleCard(article: article);
      },
    );
  }
  
  /// 显示筛选对话框
  void _showFilterDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        minChildSize: 0.3,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              // 拖拽指示器
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              
              Text(
                '筛选条件',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              
              const SizedBox(height: 16),
              
              // TODO: 添加筛选选项
              Expanded(
                child: ListView(
                  controller: scrollController,
                  children: const [
                    ListTile(
                      title: Text('全部来源'),
                      trailing: Icon(Icons.radio_button_checked),
                    ),
                    ListTile(
                      title: Text('搜索引擎'),
                      trailing: Icon(Icons.radio_button_unchecked),
                    ),
                    ListTile(
                      title: Text('微博首页'),
                      trailing: Icon(Icons.radio_button_unchecked),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}