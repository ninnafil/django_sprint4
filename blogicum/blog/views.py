from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db import models
from django.db.models import Count
from django.views.generic import DetailView, UpdateView, CreateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from blog.models import Post, Category, Comment
from .forms import PostForm, CommentForm
from django.utils import timezone


User = get_user_model()


class AuthorRequiredMixin(UserPassesTestMixin):
    """
    Миксин для проверки, что пользователь является автором объекта.
    Используется для ограничения доступа к редактированию и удалению
    постов и комментариев только их авторами.
    """

    def test_func(self):
        """Проверяет, является ли текущий пользователь автором объекта."""
        obj = self.get_object()
        return self.request.user == obj.author


class PostMixin():
    """
    Базовый миксин для всех View, работающих с моделью Post.
    Определяет общие атрибуты.
    """

    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'


class CommentMixin():
    """
    Базовый миксин для всех View, работающих с моделью Comment.
    Определяет общие атрибуты.
    """

    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'  # имя параметра URL для ID комментария

    def get_context_data(self, **kwargs):
        """
        Добавляет объект комментария в контекст
        для использования в шаблоне.
        """
        context = super().get_context_data(**kwargs)
        context['comment'] = self.object
        return context


class ProfileView(DetailView):
    """
    Страница профиля пользователя.
    Отображает информацию о пользователе и список его публикаций.
    Доступна всем посетителям, но автор видит все свои посты
    (включая отложенные и снятые с публикации), а другие пользователи
    видят только опубликованные посты с прошедшей датой публикации.
    """

    model = User
    template_name = 'blog/profile.html'
    slug_field = 'username'  # используем username как идентификатор в URL
    slug_url_kwarg = 'username'  # Имя параметра в URL
    context_object_name = 'profile'  # Имя переменной в шаблоне

    def get_context_data(self, **kwargs):
        """Добавляет посты пользователя с пагинацией в контекст шаблона."""
        # Получаем базовый контекст с profile
        context = super().get_context_data(**kwargs)
        # Получаем объект пользователя, чей профиль просматривается
        user = self.object

        # Получаем посты пользователя с оптимизацией запросов
        posts = user.blog.all().select_related(
            'category', 'location', 'author'
        ).annotate(
            comment_count=Count('comments')  # Количество комментариев
        ).order_by('-pub_date')

        # Если пользователь просматривает не свой профиль,
        # показываем только опубликованные посты с прошедшей датой
        if self.request.user != user:
            posts = posts.filter(
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now()
            )

        # Настраиваем пагинацию 10 постов на страницу
        paginator = Paginator(posts, 10)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Добавляем объект страницы в контекст
        context['page_obj'] = page_obj
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    Редактирование профиля пользователя.
    Доступно только залогиненному пользователю для редактирования
    собственного профиля. Позволяет изменить имя, фамилию,
    логин и email.
    """

    model = User
    fields = ['first_name', 'last_name', 'username', 'email']
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        """Возвращает текущего аутентифицированного пользователя."""
        return self.request.user

    def get_success_url(self):
        """
        Возвращает URL для перенаправления после успешного сохранения.
        Перенаправляет на страницу профиля текущего пользователя.
        """
        return reverse('blog:profile', kwargs={
            'username': self.request.user.username
        })


# Будут обработаны POST-запросы только от залогиненных пользователей.
class PostCreateView(LoginRequiredMixin, PostMixin, CreateView):
    """
    Создание новой публикации.
    Доступно только авторизованным пользователям. Позволяет создать
    новый пост с возможностью прикрепления изображения и установки
    отложенной публикации. Наследует общие атрибуты из PostMixin.
    """

    def form_valid(self, form):
        """
        Обрабатывает валидную форму создания поста.
        Автоматически устанавливает автора поста как текущего пользователя.
        """
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """
        Возвращает URL для перенаправления после создания поста.
        Перенаправляет на страницу профиля автора.
        """
        return reverse('blog:profile', kwargs={
            'username': self.request.user.username
        })


class PostUpdateView(LoginRequiredMixin, AuthorRequiredMixin,
                     PostMixin, UpdateView):
    """
    Редактирование существующей публикации.
    Доступно только автору публикации. Использует тот же шаблон,
    что и создание поста. Сохраняет возможность редактирования всех полей,
    включая изображение. Наследует общие атрибуты из PostMixin
    и проверку авторства из AuthorRequiredMixin.
    """

    pk_url_kwarg = 'post_id'  # Имя параметра в URL для ID поста

    def get_success_url(self):
        """
        Возвращает URL для перенаправления после редактирования.
        Перенаправляет на страницу отредактированного поста.
        """
        return reverse('blog:post_detail', kwargs={'post_id': self.object.id})


class PostDeleteView(LoginRequiredMixin, AuthorRequiredMixin,
                     PostMixin, DeleteView):
    """
    Удаление публикации.
    Доступно только автору публикации. Перед удалением показывает
    страницу подтверждения с информацией о посте. После удаления
    перенаправляет на главную страницу. Наследует общие атрибуты из PostMixin
    и проверку авторства из AuthorRequiredMixin.
    """

    pk_url_kwarg = 'post_id'  # Имя параметра в URL для ID поста
    success_url = reverse_lazy('blog:index')  # Перенаправление на главную

    def get_context_data(self, **kwargs):
        """
        Добавляет форму с данными поста в контекст для отображения.
        Необходимо для работы шаблона, который использует form.instance
        для показа информации о посте перед удалением.
        """
        context = super().get_context_data(**kwargs)
        # Создаем форму с текущим объектом для отображения в шаблоне
        form = PostForm(instance=self.object)
        context['form'] = form
        return context


class CommentUpdateView(LoginRequiredMixin, AuthorRequiredMixin,
                        CommentMixin, UpdateView):
    """
    Редактирование комментария.
    Доступно только автору комментария. Позволяет изменить текст
    существующего комментария. Наследует общие
    атрибуты из CommentMixin и проверку авторства из AuthorRequiredMixin.
    """

    def get_success_url(self):
        """
        Возвращает URL для перенаправления после редактирования комментария.
        Перенаправляет на страницу поста, к которому относится комментарий.
        """
        return reverse('blog:post_detail', kwargs={
            'post_id': self.kwargs.get('post_id')
        })


class CommentDeleteView(LoginRequiredMixin, AuthorRequiredMixin,
                        CommentMixin, DeleteView):
    """
    Удаление комментария.
    Доступно только автору комментария. Перед удалением показывает
    страницу подтверждения с текстом комментария. После удаления
    перенаправляет на страницу поста. Наследует общие
    атрибуты из CommentMixin и проверку авторства из AuthorRequiredMixin.
    """

    def get_success_url(self):
        """
        Возвращает URL для перенаправления после удаления комментария.
        Перенаправляет на страницу поста, к которому относился комментарий.
        """
        return reverse('blog:post_detail', kwargs={
            'post_id': self.kwargs.get('post_id')
        })


@login_required
def add_comment(request, post_id):
    """
    Добавление нового комментария к посту.
    Доступно только авторизованным пользователям. Обрабатывает POST-запросы
    с формой комментария. После успешного добавления перенаправляет
    на страницу поста.
    """
    post = get_object_or_404(Post, pk=post_id)

    # Обработка POST-запроса с данными формы
    if request.method == 'POST' and request.user.is_authenticated:
        form = CommentForm(request.POST)
        if form.is_valid():
            # Создаем комментарий, но не сохраняем в БД
            comment = form.save(commit=False)
            comment.post = post  # Привязываем к посту
            comment.author = request.user  # Устанавливаем автора
            comment.save()  # Сохраняем в БД
            return redirect('blog:post_detail', post_id=post_id)
    else:
        form = CommentForm()

    # GET-запрос или невалидная форма - перенаправляем на пост
    return redirect('blog:post_detail', post_id=post_id)


def index(request):
    """
    Главная страница сайта.
    Отображает список опубликованных постов с пагинацией.
    Показывает только посты с прошедшей датой публикации,
    опубликованные в опубликованных категориях.
    """
    template = 'blog/index.html'

    # Получаем опубликованные посты с оптимизацией запросов
    post_list = Post.objects.select_related(
        'category', 'author', 'location'
    ).filter(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True
    ).annotate(
        comment_count=Count('comments')  # Добавляем количество комментариев
    ).order_by('-pub_date')  # Сортировка по дате

    # Создаём объект пагинатора с количеством 10 записей на страницу.
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Подготавливаем контекст для шаблона.
    context = {'page_obj': page_obj}
    return render(request, template, context)


def category_posts(request, category_slug):
    """
    Страница постов определенной категории.
    Отображает список опубликованных постов в указанной категории
    с пагинацией. Показывает только посты с прошедшей датой публикации.
    """
    template = 'blog/category.html'
    # Получаем категорию (только опубликованную).
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True
    )
    # Получаем посты категории с оптимизацией запросов.
    post_list = Post.objects.select_related(
        'category', 'author', 'location'
    ).filter(
        category=category,
        is_published=True,
        pub_date__lte=timezone.now()
    ).annotate(
        comment_count=Count('comments')
    ).order_by('-pub_date')
    # Настраиваем пагинацию 10 постов на страницу.
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Подготавливаем словарь контекста.
    context = {'category': category, 'page_obj': page_obj}
    return render(request, template, context)


def post_detail(request, post_id):
    """
    Детальная страница поста.
    Отображает полную информацию о посте, включая комментарии.
    Автор поста видит все свои посты (включая отложенные и снятые),
    другие пользователи видят только опубликованные посты
    с прошедшей датой публикации.
    """
    template = 'blog/detail.html'

    # Получаем базовый queryset с оптимизацией запросов
    posts = Post.objects.select_related(
        'category', 'author', 'location'
    )

    # Фильтрация для разных типов пользователей
    if request.user.is_authenticated:
        # Авторизованный пользователь:
        # - Видит все свои посты (включая отложенные и снятые)
        # - Видит опубликованные посты других пользователей
        posts = posts.filter(
            models.Q(author=request.user)
            | models.Q(
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now()
            )
        )
    else:
        # Анонимный пользователь:
        # Видит только опубликованные посты с прошедшей датой
        posts = posts.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now()
        )

    # Получаем конкретный пост
    post = get_object_or_404(posts, pk=post_id)
    # Получаем комментарии к посту с оптимизацией запросов
    comments = post.comments.all().select_related('author')
    # Форма для добавления комментария (только для авторизованных)
    form = CommentForm() if request.user.is_authenticated else None

    # Подготавливаем контекст для шаблона
    context = {
        'post': post,
        'comments': comments,
        'form': form,
        'now': timezone.now(),
    }
    return render(request, template, context)
