from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponseForbidden
from datetime import timedelta
from decimal import Decimal
from .models import Book, Member, BorrowRecord
from .forms import (BookForm, BookInventoryForm, BookStatusForm, MemberUserForm, 
                    MemberStatusForm, BorrowRecordForm, CreateBorrowForm, ReturnBorrowForm, RegisterForm)

# 防止瀏覽器快取敏感頁面的 MixIn
class NoCacheMixin:
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


def no_cache_view(view_func):
    from functools import wraps

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        try:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        except Exception:
            pass
        return response

    return _wrapped


# ========== 權限檢查Mixin與裝飾器 ==========

class StaffOnlyMixin(NoCacheMixin, LoginRequiredMixin, UserPassesTestMixin):
    """
    只允許 staff 或 superuser 使用者的 Mixin
    """
    login_url = reverse_lazy('login')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, '您沒有權限訪問此頁面。只有管理者可以存取。')
        return redirect('library:home')


def staff_required(view_func):
    """
    只允許 staff 使用者的裝飾器
    """
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, '您沒有權限訪問此頁面。只有管理者可以存取。')
            return redirect('library:home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ========== 首頁與認證視圖 ==========

@require_http_methods(["GET"])
def home(request):
    """
    首頁視圖
    依據用戶身份顯示不同內容
    """
    # 常見首頁資料：熱門書籍
    top_books = Book.objects.annotate(borrow_count=Count('borrow_records')).order_by('-borrow_count')[:6]

    context = {
        'top_books': top_books,
    }

    # 若為已登入的一般會員，嘗試載入會員統計
    if request.user.is_authenticated and not request.user.is_staff:
        try:
            member = request.user.member_profile
            context.update({
                'member_profile': member,
                'member_total_borrows': member.borrow_records.count(),
                'member_active_borrows': member.borrow_records.filter(status='borrowing').count(),
            })
        except Member.DoesNotExist:
            pass

    return render(request, 'home.html', context)


@require_http_methods(["GET", "POST"])
def register(request):
    """
    新會員註冊視圖
    提供表單供新用戶完成帳號和會員資訊的註冊
    支援自動登入和導向首頁
    """
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                # 保存表單（會建立 User 和 Member）
                user = form.save()
                
                # 自動登入
                from django.contrib.auth import authenticate, login
                authenticated_user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password1'])
                if authenticated_user is not None:
                    login(request, authenticated_user)
                
                messages.success(
                    request, 
                    f'✨ 歡迎！{user.get_full_name() or user.username}，您已成功註冊並自動登入系統。'
                )
                return redirect('library:home')
            except Exception as e:
                messages.error(request, f'註冊過程發生錯誤：{str(e)}')
    else:
        form = RegisterForm()
    
    return render(request, 'auth/register.html', {'form': form})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    登出視圖
    支援 GET 請求直接登出
    """
    if request.method == 'POST' or request.method == 'GET':
        logout(request)
        messages.success(request, '您已成功登出系統。')
        return redirect('library:home')


# ========== 圖書管理視圖 ==========

class BookListView(ListView):
    """
    圖書列表視圖
    顯示所有圖書，支援搜尋和過濾
    """
    model = Book
    template_name = 'book/book_list.html'
    context_object_name = 'books'
    paginate_by = 20
    
    def get_queryset(self):
        """
        根據搜尋條件過濾圖書
        """
        queryset = Book.objects.all()
        
        # 搜尋功能：可以搜尋書名、作者、ISBN
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(author__icontains=search_query) |
                Q(isbn__icontains=search_query)
            )
        
        # 分類過濾
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # 狀態過濾
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 取得所有分類供過濾使用
        context['categories'] = Book.objects.values_list('category', flat=True).distinct()
        context['search_query'] = self.request.GET.get('search', '')
        return context


class BookDetailView(DetailView):
    """
    圖書詳細資訊視圖
    顯示單本圖書的完整資訊和借閱歷史
    """
    model = Book
    template_name = 'book/book_detail.html'
    context_object_name = 'book'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 取得該書的所有借閱紀錄
        borrow_records = self.object.borrow_records.select_related('member__user').order_by('-borrow_date')
        context['borrow_records'] = borrow_records

        # 計算目前尚未歸還的已借出數量
        context['borrowed_count'] = borrow_records.filter(
            status__in=['borrowing', 'overdue']
        ).count()

        # 總數量與可借用應該一致
        context['available_quantity'] = self.object.available_quantity
        context['total_quantity'] = self.object.total_quantity
        return context


class BookCreateView(StaffOnlyMixin, CreateView):
    """
    新書建檔視圖
    提供表單新增圖書（僅限管理者）
    """
    model = Book
    form_class = BookForm
    template_name = 'book/book_form.html'
    success_url = reverse_lazy('library:book_list')
    
    def form_valid(self, form):
        """
        表單驗證成功後的處理
        """
        messages.success(self.request, f'圖書「{form.cleaned_data["title"]}」已成功新增！')
        return super().form_valid(form)


class BookUpdateView(StaffOnlyMixin, UpdateView):
    """
    圖書資訊維護視圖
    編輯現有圖書資料（僅限管理者）
    """
    model = Book
    form_class = BookForm
    template_name = 'book/book_form.html'
    success_url = reverse_lazy('library:book_list')
    
    def form_valid(self, form):
        """
        表單驗證成功後的處理
        """
        messages.success(self.request, f'圖書「{form.cleaned_data["title"]}」已成功更新！')
        return super().form_valid(form)


class BookInventoryUpdateView(StaffOnlyMixin, UpdateView):
    """
    圖書庫存調整視圖
    盤點和調整庫存數量（僅限管理者）
    """
    model = Book
    form_class = BookInventoryForm
    template_name = 'book/book_inventory_form.html'
    success_url = reverse_lazy('library:book_list')
    
    def form_valid(self, form):
        """
        表單驗證成功後的處理
        """
        messages.success(self.request, f'圖書「{self.object.title}」的庫存已成功調整！')
        return super().form_valid(form)


@staff_required
@require_http_methods(["POST"])
def book_status_toggle(request, pk):
    """
    圖書狀態切換視圖
    將圖書狀態在「上架」和「下架」之間切換（僅限管理者）
    """
    book = get_object_or_404(Book, pk=pk)
    
    if request.method == 'POST':
        # 切換狀態
        new_status = 'unavailable' if book.status == 'available' else 'available'
        book.status = new_status
        book.save()
        
        status_label = '上架' if new_status == 'available' else '下架'
        messages.success(request, f'圖書「{book.title}」已成功{status_label}！')
    
    return redirect('library:book_detail', pk=pk)


# ========== 會員管理視圖 ==========

class MemberListView(StaffOnlyMixin, NoCacheMixin, ListView):
    """
    會員列表視圖
    顯示所有會員，支援搜尋和過濾
    """
    model = Member
    template_name = 'member/member_list.html'
    context_object_name = 'members'
    paginate_by = 20
    
    def get_queryset(self):
        """
        根據搜尋條件過濾會員
        """
        queryset = Member.objects.select_related('user').all()
        
        # 搜尋功能：可以搜尋姓名、電郵、電話
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
        
        # 狀態過濾
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-registration_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class MemberDetailView(LoginRequiredMixin, UserPassesTestMixin, NoCacheMixin, DetailView):
    """
    會員詳細資訊視圖
    顯示會員完整資訊和借閱歷史
    """
    model = Member
    template_name = 'member/member_detail.html'
    context_object_name = 'member'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 取得該會員的所有借閱紀錄
        context['borrow_records'] = self.object.borrow_records.all().order_by('-borrow_date')
        # 計算統計資訊
        context['total_borrows'] = self.object.borrow_records.count()
        context['active_borrows'] = self.object.borrow_records.filter(status='borrowing').count()
        return context

    def test_func(self):
        # 管理員可以查看任意會員，普通會員只能查看自己的資料
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        # 非管理員只能查看與自身關聯的 Member
        return self.get_object().user == self.request.user

    def handle_no_permission(self):
        messages.error(self.request, '您沒有權限查看該會員資料。')
        return redirect('library:home')


class MemberCreateView(StaffOnlyMixin, NoCacheMixin, CreateView):
    """
    新增會員視圖
    提供表單新增會員和帳號（僅限管理者）
    """
    model = Member
    form_class = MemberUserForm
    template_name = 'member/member_form.html'
    success_url = reverse_lazy('library:member_list')
    
    def get_form_kwargs(self):
        """
        傳遞 member=None 給表單（表示新建）
        """
        kwargs = super().get_form_kwargs()
        kwargs['member'] = None
        return kwargs
    
    def form_valid(self, form):
        """
        表單驗證成功後的處理
        """
        member = form.save()
        full_name = f"{member.user.last_name}{member.user.first_name}" or member.user.username
        messages.success(self.request, f'會員「{full_name}」已成功新增！')
        return super().form_valid(form)


class MemberUpdateView(LoginRequiredMixin, UserPassesTestMixin, NoCacheMixin, UpdateView):
    """
    修改會員資料視圖
    編輯會員和帳號資訊（僅限管理者）
    """
    model = Member
    form_class = MemberUserForm
    template_name = 'member/member_form.html'
    success_url = reverse_lazy('library:member_list')
    
    def get_form(self, form_class=None):
        """
        自訂表單初始化，傳遞 member 實例
        """
        if form_class is None:
            form_class = self.get_form_class()
        
        if self.request.method in ('POST', 'PUT'):
            return form_class(self.request.POST, member=self.object)
        else:
            return form_class(member=self.object)
    
    def form_valid(self, form):
        """
        表單驗證成功後的處理
        """
        member = form.save()
        full_name = f"{member.user.last_name}{member.user.first_name}" or member.user.username
        messages.success(self.request, f'會員「{full_name}」的資料已成功更新！')
        return redirect(self.success_url)

    def test_func(self):
        # 管理員可編輯任意會員；普通會員只能編輯自己的會員資料
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        return self.get_object().user == self.request.user

    def handle_no_permission(self):
        messages.error(self.request, '您沒有權限編輯該會員資料。')
        return redirect('library:home')


@staff_required
@require_http_methods(["POST"])
def member_status_toggle(request, pk):
    """
    會員狀態切換視圖
    在「正常」和「停權」之間切換會員狀態（僅限管理者）
    """
    member = get_object_or_404(Member, pk=pk)
    
    if request.method == 'POST':
        # 切換狀態
        new_status = 'suspended' if member.status == 'active' else 'active'
        member.status = new_status
        member.save()
        
        status_label = '已恢復' if new_status == 'active' else '已停權'
        member_name = member.user.get_full_name() or member.user.username
        messages.success(request, f'會員「{member_name}」{status_label}！')
    
    return redirect('library:member_detail', pk=pk)


# ========== 借閱管理視圖 ==========

@staff_required
@require_http_methods(["GET", "POST"])
def borrow_create(request):
    """
    建立借閱紀錄視圖
    驗證會員資格和圖書庫存，然後建立借閱紀錄（僅限管理者）
    """
    if request.method == 'POST':
        form = CreateBorrowForm(request.POST)
        if form.is_valid():
            member = form.cleaned_data['member']
            book = form.cleaned_data['book']
            
            try:
                # 使用 atomic 事務確保數據一致性
                with transaction.atomic():
                    # 再次驗證會員狀態（防止競態條件）
                    member.refresh_from_db()
                    if member.status == 'suspended':
                        member_name = member.user.get_full_name() or member.user.username
                        messages.error(request, f'會員「{member_name}」已停權，無法借書。')
                        return redirect('library:borrow_create')
                    
                    if member.outstanding_fine > 0:
                        messages.error(request, f'會員有未繳罰款 NT$ {member.outstanding_fine}，請先清除罰款。')
                        return redirect('library:borrow_create')
                    
                    # 再次驗證圖書庫存（防止競態條件）
                    book.refresh_from_db()
                    if book.available_quantity <= 0:
                        messages.error(request, f'圖書「{book.title}」暫無可借館藏。')
                        return redirect('library:borrow_create')
                    
                    if book.status != 'available':
                        messages.error(request, f'圖書「{book.title}」已下架，無法借出。')
                        return redirect('library:borrow_create')
                    
                    # 建立借閱紀錄
                    borrow_date = timezone.now()
                    due_date = borrow_date.date() + timedelta(days=14)
                    
                    borrow_record = BorrowRecord.objects.create(
                        member=member,
                        book=book,
                        due_date=due_date,
                        status='borrowing',
                        borrow_date=borrow_date,
                    )
                    
                    # 減少圖書庫存
                    book.available_quantity -= 1
                    book.save(update_fields=['available_quantity'])
                    
                    messages.success(
                        request,
                        f'借閱成功！會員「{member.user.get_full_name() or member.user.username}」借取《{book.title}》，'
                        f'應於 {due_date} 前歸還。'
                    )
                    
                    return redirect('library:borrow_receipt', pk=borrow_record.pk)
                    
            except Exception as e:
                messages.error(request, f'借閱失敗：{str(e)}')
                return redirect('library:borrow_create')
    else:
        form = CreateBorrowForm()
    
    return render(request, 'borrow/borrow_form.html', {'form': form})


@staff_required
@require_http_methods(["GET"])
def borrow_receipt(request, pk):
    """
    借閱收據視圖
    顯示剛建立的借閱紀錄詳情（僅限管理者）
    """
    # 使用 select_related 一次取出 BorrowRecord 關聯的 Member -> User 與 Book，避免額外查詢
    borrow_record = get_object_or_404(
        BorrowRecord.objects.select_related('member__user', 'book'),
        pk=pk
    )

    member = borrow_record.member
    # 預先計算並傳遞會員顯示名稱與 email 給 template，template 可直接使用 member_name / member_email
    member_name = member.user.get_full_name() or member.user.username
    member_email = member.user.email

    context = {
        'borrow_record': borrow_record,
        'member': member,
        'book': borrow_record.book,
        'member_name': member_name,
        'member_email': member_email,
    }
    
    return render(request, 'borrow/borrow_receipt.html', context)


@staff_required
@require_http_methods(["GET", "POST"])
def borrow_search(request):
    """
    還書搜尋視圖
    使用關鍵字搜尋會員名稱或書名，顯示所有未歸還的紀錄
    """
    search_results = None
    search_keyword = None
    
    if request.method == 'POST':
        form = ReturnBorrowForm(request.POST)
        if form.is_valid():
            keyword = form.cleaned_data['keyword'].strip()
            
            # 關鍵字搜尋：同時比對會員名稱和書名
            search_results = BorrowRecord.objects.filter(
                status__in=['borrowing', 'overdue']
            ).filter(
                Q(member__user__first_name__icontains=keyword) |
                Q(member__user__last_name__icontains=keyword) |
                Q(member__user__username__icontains=keyword) |
                Q(book__title__icontains=keyword) |
                Q(book__author__icontains=keyword)
            ).select_related('member', 'book').order_by('-borrow_date')
            
            if not search_results.exists():
                messages.error(request, f'找不到匹配「{keyword}」的待還紀錄。')
                return redirect('library:borrow_search')
            
            search_keyword = keyword
    else:
        form = ReturnBorrowForm()
    
    return render(request, 'borrow/borrow_search.html', {
        'form': form,
        'search_results': search_results,
        'search_keyword': search_keyword
    })


@staff_required
@require_http_methods(["GET", "POST"])
def borrow_return(request, pk):
    """
    還書視圖
    處理還書邏輯，計算罰款，更新庫存（僅限管理者）
    """
    borrow_record = get_object_or_404(
        BorrowRecord.objects.select_related('member__user', 'book'),
        pk=pk
    )
    
    # 確保只能還「借閱中」或「已逾期」的紀錄
    if borrow_record.status not in ['borrowing', 'overdue']:
        messages.error(request, '此借閱紀錄已完成，無法再次還書。')
        return redirect('library:borrow_search')

    today = timezone.now().date()
    overdue_days = max(0, (today - borrow_record.due_date).days)
    overdue_fine = Decimal('0.00')
    if overdue_days > 0:
        overdue_fine = Decimal(overdue_days) * Decimal('10.00')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 重新取得記錄以確保最新狀態
                borrow_record = BorrowRecord.objects.select_for_update().get(pk=pk)
                
                # 取得相關對象
                member = borrow_record.member
                book = borrow_record.book
                
                # 計算罰款
                today = timezone.now().date()
                overdue_fine_amount = Decimal('0.00')
                
                if today > borrow_record.due_date:
                    overdue_days = (today - borrow_record.due_date).days
                    daily_fine = Decimal('10.00')  # 每天 10 元
                    overdue_fine_amount = Decimal(overdue_days) * daily_fine
                
                # 更新借閱紀錄
                borrow_record.return_date = today
                borrow_record.overdue_fine = overdue_fine_amount
                
                # 判斷是否逾期
                if today > borrow_record.due_date:
                    borrow_record.status = 'overdue'
                else:
                    borrow_record.status = 'returned'
                
                borrow_record.save(update_fields=['return_date', 'overdue_fine', 'status'])
                
                # 如果有罰款，更新會員的未繳罰款總額
                if overdue_fine_amount > 0:
                    member.outstanding_fine += overdue_fine_amount
                    member.save(update_fields=['outstanding_fine'])
                
                # 增加圖書庫存
                book.available_quantity += 1
                book.save(update_fields=['available_quantity'])
                
                # 記錄成功訊息
                if overdue_fine_amount > 0:
                    messages.success(
                        request,
                        f'還書成功！書籍「{book.title}」已歸還。'
                        f'逾期罰款：NT$ {overdue_fine_amount}，'
                        f'已加入會員帳戶。'
                    )
                else:
                    messages.success(
                        request,
                        f'還書成功！書籍「{book.title}」已按時歸還。'
                    )
                
                return redirect('library:return_receipt', pk=borrow_record.pk)
                
        except Exception as e:
            messages.error(request, f'還書失敗：{str(e)}')
            return redirect('library:borrow_search')
    
    context = {
        'borrow_record': borrow_record,
        'member': borrow_record.member,
        'book': borrow_record.book,
        'today': today,
        'overdue_days': overdue_days,
        'overdue_fine': overdue_fine,
        'return_status': '逾期歸還' if overdue_days > 0 else '準時歸還',
    }
    
    return render(request, 'borrow/borrow_return.html', context)


@staff_required
@require_http_methods(["GET"])
def return_receipt(request, pk):
    """
    還書收據視圖
    顯示還書完成的詳細資訊和罰款（僅限管理者）
    """
    borrow_record = get_object_or_404(
        BorrowRecord.objects.select_related('member__user', 'book'),
        pk=pk
    )
    
    # 計算逾期天數
    if borrow_record.return_date and borrow_record.due_date:
        overdue_days = max(0, (borrow_record.return_date - borrow_record.due_date).days)
    else:
        overdue_days = 0
    
    context = {
        'borrow_record': borrow_record,
        'member': borrow_record.member,
        'book': borrow_record.book,
        'overdue_days': overdue_days,
    }
    
    return render(request, 'borrow/return_receipt.html', context)


# ========== 查詢與報表視圖 ==========

@require_http_methods(["GET"])
def search_book(request):
    """
    搜尋圖書視圖
    用戶和管理員都能使用的查詢頁面
    """
    books = Book.objects.all()
    search_query = request.GET.get('q', '')
    
    if search_query:
        books = books.filter(
            Q(title__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    # 為每本書計算庫存百分比
    for book in books:
        if book.total_quantity > 0:
            book.available_percent = round((book.available_quantity / book.total_quantity) * 100, 0)
        else:
            book.available_percent = 0
    
    context = {
        'books': books,
        'search_query': search_query,
        'total_results': books.count(),
    }
    
    return render(request, 'reports/search_book.html', context)


@staff_required
@require_http_methods(["GET"])
def inventory_dashboard(request):
    """
    館藏統計報表視圖
    顯示系統的統計數據和分類統計（僅限管理者）
    """
    # 總體統計
    total_books = Book.objects.count()
    total_quantity = Book.objects.aggregate(Sum('total_quantity'))['total_quantity__sum'] or 0
    available_quantity = Book.objects.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0
    borrowed_quantity = total_quantity - available_quantity
    
    # 會員統計
    total_members = Member.objects.count()
    active_members = Member.objects.filter(status='active').count()
    suspended_members = Member.objects.filter(status='suspended').count()
    
    # 借閱統計
    total_borrows = BorrowRecord.objects.count()
    borrowing_count = BorrowRecord.objects.filter(status='borrowing').count()
    returned_count = BorrowRecord.objects.filter(status='returned').count()
    overdue_count = BorrowRecord.objects.filter(status='overdue').count()
    
    # 分類統計
    category_stats = Book.objects.values('category').annotate(
        total=Count('id'),
        available=Sum(
            'available_quantity'
        )
    ).order_by('-total')
    
    # 狀態統計
    status_stats = Book.objects.values('status').annotate(count=Count('id'))
    
    # 未繳罰款總額
    total_outstanding_fine = Member.objects.aggregate(Sum('outstanding_fine'))['outstanding_fine__sum'] or Decimal('0.00')
    
    # 最近的摘要數據（最近 7 天的借閱）
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_borrows = BorrowRecord.objects.filter(borrow_date__gte=seven_days_ago).count()
    recent_returns = BorrowRecord.objects.filter(return_date__gte=seven_days_ago).count()
    
    context = {
        'total_books': total_books,
        'total_quantity': total_quantity,
        'available_quantity': available_quantity,
        'borrowed_quantity': borrowed_quantity,
        'borrow_rate': round((borrowed_quantity / total_quantity * 100), 2) if total_quantity > 0 else 0,
        'total_members': total_members,
        'active_members': active_members,
        'suspended_members': suspended_members,
        'total_borrows': total_borrows,
        'borrowing_count': borrowing_count,
        'returned_count': returned_count,
        'overdue_count': overdue_count,
        'category_stats': category_stats,
        'status_stats': status_stats,
        'total_outstanding_fine': total_outstanding_fine,
        'recent_borrows': recent_borrows,
        'recent_returns': recent_returns,
    }
    
    return render(request, 'reports/inventory_dashboard.html', context)


@staff_required
@require_http_methods(["GET"])
def borrow_ranking(request):
    """
    借閱排行榜視圖
    統計並列出歷史以來借閱次數最高的 Top 10 圖書（僅限管理者）
    """
    top_borrowed = Book.objects.annotate(
        borrow_count=Count('borrow_records')
    ).order_by('-borrow_count')[:10]
    
    context = {
        'top_borrowed': top_borrowed,
    }
    
    return render(request, 'reports/borrow_ranking.html', context)


@staff_required
@require_http_methods(["GET"])
def borrow_report(request):
    """
    借閱/逾期清單報表視圖
    提供給管理員查看的清單頁面，支持篩選（僅限管理者）
    """
    # 預設過濾
    filter_type = request.GET.get('filter', 'all')
    
    borrows = BorrowRecord.objects.select_related('member', 'book')
    
    if filter_type == 'borrowing':
        borrows = borrows.filter(status='borrowing')
    elif filter_type == 'overdue':
        borrows = borrows.filter(status='overdue')
    elif filter_type == 'returned':
        borrows = borrows.filter(status='returned')
    
    # 排序：最新的在前
    borrows = borrows.order_by('-borrow_date')
    
    # 計算統計
    all_count = BorrowRecord.objects.count()
    borrowing_count = BorrowRecord.objects.filter(status='borrowing').count()
    overdue_count = BorrowRecord.objects.filter(status='overdue').count()
    returned_count = BorrowRecord.objects.filter(status='returned').count()
    
    # 計算逾期罰款總額
    total_overdue_fine = BorrowRecord.objects.filter(status='overdue').aggregate(
        Sum('overdue_fine')
    )['overdue_fine__sum'] or Decimal('0.00')
    
    context = {
        'borrows': borrows,
        'filter_type': filter_type,
        'all_count': all_count,
        'borrowing_count': borrowing_count,
        'overdue_count': overdue_count,
        'returned_count': returned_count,
        'total_overdue_fine': total_overdue_fine,
        'current_count': borrows.count(),
    }
    
    return render(request, 'reports/borrow_report.html', context)


# ========== 會員個人專屬視圖 ==========

@login_required
@require_http_methods(["GET"])
@no_cache_view
def my_borrows(request):
    """
    我的借閱紀錄視圖
    讓一般會員查看自己的借閱歷史
    """
    try:
        member = request.user.member_profile
    except Member.DoesNotExist:
        messages.error(request, '您的會員檔案尚未建立。請聯絡圖書館管理員。')
        return redirect('library:home')
    
    # 取得該會員的所有借閱紀錄
    borrow_records = BorrowRecord.objects.filter(member=member).select_related('book').order_by('-borrow_date')
    
    # 統計會員的借閱狀態
    context = {
        'member': member,
        'borrow_records': borrow_records,
        'total_borrows': borrow_records.count(),
        'active_borrows': borrow_records.filter(status='borrowing').count(),
        'overdue_borrows': borrow_records.filter(status='overdue').count(),
        'returned_borrows': borrow_records.filter(status='returned').count(),
        'outstanding_fine': member.outstanding_fine,
    }
    
    return render(request, 'member/my_borrows.html', context)


@login_required
@require_http_methods(["GET"])
@no_cache_view
def profile(request):
    """
    簡單導向使用者自己的會員詳細頁面
    """
    try:
        member = request.user.member_profile
    except Member.DoesNotExist:
        messages.error(request, '您的會員檔案尚未建立。請聯絡管理員。')
        return redirect('library:home')

    return redirect('library:member_detail', pk=member.pk)

