from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    # ========== 首頁 ==========
    path('', views.home, name='home'),
    
    # ========== 認證 ==========
    path('register/', views.register, name='register'),
    
    # ========== 圖書管理 ==========
    # 圖書列表
    path('books/', views.BookListView.as_view(), name='book_list'),
    
    # 圖書詳細資訊
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    
    # 新書建檔
    path('books/create/', views.BookCreateView.as_view(), name='book_create'),
    
    # 圖書資訊維護
    path('books/<int:pk>/edit/', views.BookUpdateView.as_view(), name='book_edit'),
    
    # 圖書庫存調整
    path('books/<int:pk>/inventory/', views.BookInventoryUpdateView.as_view(), name='book_inventory'),
    
    # 館藏下架/上架（狀態切換）
    path('books/<int:pk>/toggle-status/', views.book_status_toggle, name='book_toggle_status'),
    
    # ========== 會員管理 ==========
    # 會員列表
    path('members/', views.MemberListView.as_view(), name='member_list'),
    
    # 會員詳細資訊（含借閱歷史）
    path('members/<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    
    # 新增會員
    path('members/create/', views.MemberCreateView.as_view(), name='member_create'),
    
    # 修改會員資料
    path('members/<int:pk>/edit/', views.MemberUpdateView.as_view(), name='member_edit'),
    
    # 會員停權/解鎖（狀態切換）
    path('members/<int:pk>/toggle-status/', views.member_status_toggle, name='member_toggle_status'),
    
    # ========== 借閱管理 ==========
    # 建立借閱紀錄
    path('borrow/create/', views.borrow_create, name='borrow_create'),
    
    # 借閱收據
    path('borrow/<int:pk>/receipt/', views.borrow_receipt, name='borrow_receipt'),
    
    # 還書搜尋
    path('borrow/search/', views.borrow_search, name='borrow_search'),
    
    # 還書處理
    path('borrow/<int:pk>/return/', views.borrow_return, name='borrow_return'),
    
    # 還書收據
    path('borrow/<int:pk>/return-receipt/', views.return_receipt, name='return_receipt'),
    
    # ========== 查詢與報表 ==========
    # 搜尋圖書
    path('search/', views.search_book, name='search_book'),
    
    # 館藏統計報表
    path('reports/inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    
    # 借閱排行榜
    path('reports/ranking/', views.borrow_ranking, name='borrow_ranking'),
    
    # 借閱/逾期清單報表
    path('reports/borrow/', views.borrow_report, name='borrow_report'),
    
    # ========== 會員個人專屬 ==========
    # 我的借閱紀錄
    path('my-borrows/', views.my_borrows, name='my_borrows'),
]

