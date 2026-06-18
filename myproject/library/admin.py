from django.contrib import admin
from .models import Member, Book, BorrowRecord


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """
    會員管理後台
    整合了 Django User 模型和 Member 模型的信息
    """
    list_display = ['get_username', 'get_full_name', 'get_email', 'phone', 'status', 'outstanding_fine', 'registration_date']
    list_filter = ['status', 'registration_date', 'user__is_staff']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'user__email', 'phone']
    readonly_fields = ['registration_date', 'user']
    
    fieldsets = (
        ('帳號資訊', {
            'fields': ('user',),
            'description': '此會員關聯的系統帳號'
        }),
        ('聯絡資訊', {
            'fields': ('phone',)
        }),
        ('會員狀態', {
            'fields': ('status', 'outstanding_fine')
        }),
        ('系統資訊', {
            'fields': ('registration_date',),
            'classes': ('collapse',)
        }),
    )
    
    def get_username(self, obj):
        """
        顯示帳號名稱
        """
        return obj.user.username
    get_username.short_description = '帳號'
    get_username.admin_order_field = 'user__username'
    
    def get_full_name(self, obj):
        """
        顯示會員全名
        """
        full_name = obj.user.get_full_name()
        return full_name if full_name else '(未設定)'
    get_full_name.short_description = '名稱'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_email(self, obj):
        """
        顯示會員電郵
        """
        return obj.user.email
    get_email.short_description = '電郵'
    get_email.admin_order_field = 'user__email'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """
    圖書管理後台
    """
    list_display = ['title', 'author', 'isbn', 'category', 'available_quantity', 'total_quantity', 'status', 'created_date']
    list_filter = ['status', 'category', 'created_date']
    search_fields = ['title', 'author', 'isbn']
    readonly_fields = ['created_date']
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('title', 'author', 'isbn', 'publisher')
        }),
        ('分類與狀態', {
            'fields': ('category', 'status')
        }),
        ('庫存管理', {
            'fields': ('total_quantity', 'available_quantity'),
            'description': '總數量為購入冊數，庫存數量為目前可借用的冊數'
        }),
        ('系統資訊', {
            'fields': ('created_date',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    """
    借閱紀錄管理後台
    """
    list_display = ['get_record_id', 'get_member_name', 'book', 'borrow_date', 'due_date', 'return_date', 'status', 'overdue_fine']
    list_filter = ['status', 'borrow_date', 'due_date']
    search_fields = ['member__user__username', 'member__user__first_name', 'member__user__last_name', 'member__user__email', 'book__title', 'book__isbn']
    readonly_fields = ['borrow_date', 'member', 'book']
    
    fieldsets = (
        ('借閱信息', {
            'fields': ('member', 'book', 'borrow_date')
        }),
        ('時程管理', {
            'fields': ('due_date', 'return_date', 'status')
        }),
        ('罰款信息', {
            'fields': ('overdue_fine',)
        }),
    )
    
    def get_record_id(self, obj):
        """
        顯示紀錄 ID
        """
        return f'#{obj.pk}'
    get_record_id.short_description = 'ID'
    get_record_id.admin_order_field = 'pk'
    
    def get_member_name(self, obj):
        """
        顯示會員名稱
        """
        return obj.member.user.get_full_name() or obj.member.user.username
    get_member_name.short_description = '會員'
    get_member_name.admin_order_field = 'member__user__username'

