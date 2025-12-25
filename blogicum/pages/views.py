from django.views.generic import TemplateView


# Create your views here.

class About(TemplateView):
    """Статичная страница с информацией о проекте"""

    template_name = 'pages/about.html'


class Rules(TemplateView):
    """Статичная страница с описанием правил сайта"""

    template_name = 'pages/rules.html'
