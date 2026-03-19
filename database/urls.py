from django.urls import path

from . import views

app_name = 'database'

urlpatterns = [
    path('', views.BrowserHomeView.as_view(), name='browser-home'),
    path('studies/', views.StudyListView.as_view(), name='study-list'),
    path('studies/<int:pk>/', views.StudyDetailView.as_view(), name='study-detail'),
    path('groups/', views.GroupListView.as_view(), name='group-list'),
    path('groups/<int:pk>/', views.GroupDetailView.as_view(), name='group-detail'),
    path('comparisons/', views.ComparisonListView.as_view(), name='comparison-list'),
    path('comparisons/<int:pk>/', views.ComparisonDetailView.as_view(), name='comparison-detail'),
    path('taxa/', views.TaxonListView.as_view(), name='taxon-list'),
    path('taxa/<int:pk>/', views.TaxonDetailView.as_view(), name='taxon-detail'),
    path(
        'qualitative-findings/',
        views.QualitativeFindingListView.as_view(),
        name='qualitativefinding-list',
    ),
    path(
        'qualitative-findings/<int:pk>/',
        views.QualitativeFindingDetailView.as_view(),
        name='qualitativefinding-detail',
    ),
    path(
        'quantitative-findings/',
        views.QuantitativeFindingListView.as_view(),
        name='quantitativefinding-list',
    ),
    path(
        'quantitative-findings/<int:pk>/',
        views.QuantitativeFindingDetailView.as_view(),
        name='quantitativefinding-detail',
    ),
]
