from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Post, Category, Location, Comment


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Этот email уже используется.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('title', 'text', 'pub_date', 'location', 'category', 'image')

        widgets = {
            'pub_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 7,
                'placeholder': 'Текст публикации'
            }),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

        help_texts = {
            'pub_date': 'Если установить дату и время в будущем — '
                        'можно делать отложенные публикации.',
            'image': 'Загрузите изображение для публикации (необязательно)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Фильтруем только опубликованные категории и локации
        self.fields['category'].queryset = Category.objects.filter(
            is_published=True
        ).order_by('title')

        self.fields['location'].queryset = Location.objects.filter(
            is_published=True
        ).order_by('name')

        # Устанавливаем текущую дату по умолчанию для нового поста
        if not self.instance.pk:
            now = timezone.now()
            self.initial['pub_date'] = now.strftime('%Y-%m-%dT%H:%M')

        # Для редактирования - форматируем дату из объекта
        elif self.instance.pub_date:
            self.initial['pub_date'] = self.instance.pub_date.strftime('%Y-%m-%dT%H:%M')


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Оставьте комментарий...'
            }),
        }
        labels = {
            'text': '',
        }
