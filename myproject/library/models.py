from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Member(models.Model):
    """
    會員模型
    記錄圖書館會員的基本信息及狀態
    與 Django User 模型綁定用於帳號登入
    """
    # 會員狀態選項
    STATUS_CHOICES = [
        ('active', '正常'),
        ('suspended', '停權'),
    ]

    # 與 Django User 模型的一對一關聯
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='member_profile',
        verbose_name='帳號',
        help_text='關聯的系統帳號'
    )

    phone = models.CharField(
        max_length=20,
        verbose_name='電話',
        help_text='會員聯絡電話'
    )
    registration_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='註冊日期',
        help_text='會員註冊時間'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='會員狀態',
        help_text='會員當前狀態（正常/停權）'
    )
    outstanding_fine = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='未繳罰款總額',
        help_text='會員目前未繳納的罰款總額'
    )

    class Meta:
        verbose_name = '會員'
        verbose_name_plural = '會員'
        ordering = ['-registration_date']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.user.email})'


class Book(models.Model):
    """
    圖書模型
    記錄圖書館中的圖書信息及庫存狀態
    """
    # 圖書狀態選項
    STATUS_CHOICES = [
        ('available', '上架'),
        ('unavailable', '下架'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='書名',
        help_text='圖書標題'
    )
    author = models.CharField(
        max_length=100,
        verbose_name='作者',
        help_text='圖書作者名稱'
    )
    isbn = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='ISBN',
        help_text='國際標準書號'
    )
    publisher = models.CharField(
        max_length=100,
        verbose_name='出版商',
        help_text='圖書出版社'
    )
    category = models.CharField(
        max_length=50,
        verbose_name='分類',
        help_text='圖書分類（如：文學、歷史、科技等）'
    )
    created_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='建檔日期',
        help_text='圖書建檔時間'
    )
    total_quantity = models.IntegerField(
        default=1,
        verbose_name='總數量',
        help_text='圖書館購入該書的總冊數'
    )
    available_quantity = models.IntegerField(
        default=1,
        verbose_name='庫存數量',
        help_text='該書目前可借用的冊數'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        verbose_name='狀態',
        help_text='圖書當前狀態（上架/下架）'
    )

    class Meta:
        verbose_name = '圖書'
        verbose_name_plural = '圖書'
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['isbn']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f'{self.title} - {self.author} (ISBN: {self.isbn})'


class BorrowRecord(models.Model):
    """
    借閱紀錄模型
    記錄會員的圖書借閱歷史及狀態
    """
    # 借閱狀態選項
    STATUS_CHOICES = [
        ('borrowing', '借閱中'),
        ('returned', '已歸還'),
        ('overdue', '已逾期'),
    ]

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        verbose_name='會員',
        help_text='借閱會員',
        related_name='borrow_records'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        verbose_name='圖書',
        help_text='被借閱的圖書',
        related_name='borrow_records'
    )
    borrow_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='借閱日期',
        help_text='借書時間'
    )
    due_date = models.DateField(
        verbose_name='應還日期',
        help_text='應該歸還的日期'
    )
    return_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='實際歸還日期',
        help_text='實際歸還的日期（未歸還則為空）'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='borrowing',
        verbose_name='狀態',
        help_text='借閱狀態（借閱中/已歸還/已逾期）'
    )
    overdue_fine = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='逾期罰款金額',
        help_text='因逾期產生的罰款金額'
    )

    class Meta:
        verbose_name = '借閱紀錄'
        verbose_name_plural = '借閱紀錄'
        ordering = ['-borrow_date']
        indexes = [
            models.Index(fields=['member', 'status']),
            models.Index(fields=['book', 'status']),
        ]

    def __str__(self):
        return f'{self.member.name} - {self.book.title} ({self.get_status_display()})'
