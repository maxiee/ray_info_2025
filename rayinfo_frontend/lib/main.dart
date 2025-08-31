import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'core/themes/app_theme.dart';
import 'core/constants/app_constants.dart';
import 'core/network/api_client.dart';
import 'data/datasources/api_datasource.dart';
import 'data/repositories/article_repository_impl.dart';
import 'domain/usecases/get_articles.dart';
import 'domain/usecases/search_articles.dart';
import 'domain/usecases/get_sources.dart';
import 'presentation/bloc/articles/articles_bloc.dart';
import 'presentation/bloc/search/search_bloc.dart';
import 'presentation/bloc/read_status/read_status_bloc.dart';
import 'presentation/bloc/sources/sources_bloc.dart';
import 'presentation/pages/home_page.dart';
import 'presentation/pages/search_page.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    // 初始化依赖注入
    final apiClient = ApiClient();
    final apiDataSource = ApiDataSourceImpl(apiClient);
    final articleRepository = ArticleRepositoryImpl(apiDataSource);
    final getArticlesUseCase = GetArticlesUseCase(articleRepository);
    final searchArticlesUseCase = SearchArticlesUseCase(articleRepository);
    final getSourcesUseCase = GetSourcesUseCase(articleRepository);

    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (context) => ArticlesBloc(getArticlesUseCase)),
        BlocProvider(create: (context) => SearchBloc(searchArticlesUseCase)),
        BlocProvider(
          create: (context) => ReadStatusBloc(repository: articleRepository),
        ),
        BlocProvider(
          create: (context) =>
              SourcesBloc(getSourcesUseCase: getSourcesUseCase),
        ),
      ],
      child: MaterialApp(
        title: AppConstants.appName,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const HomePage(),
        routes: {'/search': (context) => const SearchPage()},
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
