from django import forms
from django.contrib.auth.models import User
from .models import Book, Member, BorrowRecord


class BookForm(forms.ModelForm):
    """
    圖書表單
    用於新增和編輯圖書資訊
    """
    class Meta:
        model = Book
        fields = ['title', 'author', 'isbn', 'publisher', 'category', 'total_quantity', 'available_quantity', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '請輸入書名',
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '請輸入作者名稱',
            }),
            'isbn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '請輸入 ISBN（例如：978-7-1234-5678-9）',
            }),
            'publisher': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '請輸入出版商',
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '請輸入分類（例如：文學、歷史、科技）',
            }),
            'total_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '購入冊數',
                'min': '1',
            }),
            'available_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '可借用冊數',
                'min': '0',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class BookInventoryForm(forms.ModelForm):
    """
    圖書庫存調整表單
    用於盤點和調整庫存數量
    """
    class Meta:
        model = Book
        fields = ['total_quantity', 'available_quantity']
        widgets = {
            'total_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '總冊數',
                'min': '1',
            }),
            'available_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '可借用冊數',
                'min': '0',
            }),
        }


class BookStatusForm(forms.ModelForm):
    """
    圖書狀態表單
    用於快速更改圖書狀態（上架/下架）
    """
    class Meta:
        model = Book
        fields = ['status']
        widgets = {
            'status': forms.RadioSelect(attrs={
                'class': 'form-check-input',
            }),
        }


class MemberUserForm(forms.Form):
    """
    會員與帳號整合表單
    用於新增和編輯會員，同時處理 User 和 Member 的資料
    """
    # User 相關欄位
    username = forms.CharField(
        label='帳號',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入帳號（用於登入）',
        }),
        help_text='英文字母、數字和 @ / . / + / - / _ 符號'
    )
    
    first_name = forms.CharField(
        label='名字',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例如：小明',
        })
    )
    
    last_name = forms.CharField(
        label='姓氏',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例如：王',
        })
    )
    
    email = forms.EmailField(
        label='電郵',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入電子郵件',
        })
    )
    
    password = forms.CharField(
        label='密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入密碼',
        }),
        required=False,
        help_text='留空時不更改密碼'
    )
    
    # Member 相關欄位
    phone = forms.CharField(
        label='電話',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入聯絡電話（例如：0912-345-678）',
        })
    )
    
    status = forms.ChoiceField(
        label='會員狀態',
        choices=Member.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    def __init__(self, *args, member=None, **kwargs):
        # 處理 Django CreateView/UpdateView 傳遞的 instance 參數
        instance = kwargs.pop('instance', None)
        if instance and not member:
            # 試著從 instance 獲取相關的 member (如果 instance 是 Member)
            if isinstance(instance, Member):
                member = instance
        
        super().__init__(*args, **kwargs)
        self.member = member
        self.user = member.user if member else None
        
        # 編輯時預填已有資料
        if self.user:
            self.fields['username'].widget.attrs['readonly'] = True
            self.fields['username'].help_text = '帳號無法修改'
            self.fields['password'].label = '新密碼（留空不修改）'
            self.fields['password'].required = False
            
            # 預填 User 資料
            self.fields['username'].initial = self.user.username
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
            
            # 預填 Member 資料
            self.fields['phone'].initial = member.phone
            self.fields['status'].initial = member.status
    
    def clean_username(self):
        """
        驗證帳號唯一性（新建時）
        """
        username = self.cleaned_data['username']
        
        # 編輯時允許相同帳號
        if self.user:
            return username
        
        # 新建時檢查帳號是否已存在
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('此帳號已被使用，請選擇其他帳號。')
        
        return username
    
    def clean_email(self):
        """
        驗證電郵唯一性
        """
        email = self.cleaned_data['email']
        
        # 編輯時允許相同電郵
        if self.user:
            if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
                raise forms.ValidationError('此電郵已被使用，請選擇其他電郵。')
            return email
        
        # 新建時檢查電郵是否已存在
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('此電郵已被使用，請選擇其他電郵。')
        
        return email
    
    def clean_password(self):
        """
        驗證密碼（新建時必填）
        """
        password = self.cleaned_data['password']
        
        # 新建時密碼是必填的
        if not self.user and not password:
            raise forms.ValidationError('新增會員時必須設定密碼。')
        
        # 密碼長度限制
        if password and len(password) < 8:
            raise forms.ValidationError('密碼長度至少 8 個字元。')
        
        return password
    
    def save(self, commit=True):
        """
        同時保存 User 和 Member
        """
        # 處理 User
        if self.user:
            # 編輯現有 User
            user = self.user
        else:
            # 新建 User
            user = User()
        
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # 設定密碼（若有提供）
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        
        if commit:
            user.save()
        
        # 處理 Member
        if self.member:
            member = self.member
        else:
            member = Member(user=user)
        
        member.phone = self.cleaned_data['phone']
        member.status = self.cleaned_data['status']
        
        if commit:
            member.save()
        
        return member


class MemberStatusForm(forms.ModelForm):
    """
    會員狀態表單
    用於快速切換會員狀態（正常/停權）
    """
    class Meta:
        model = Member
        fields = ['status']
        widgets = {
            'status': forms.RadioSelect(attrs={
                'class': 'form-check-input',
            }),
        }


class BorrowRecordForm(forms.ModelForm):
    """
    借閱紀錄表單
    用於新增和編輯借閱紀錄
    """
    class Meta:
        model = BorrowRecord
        fields = ['member', 'book', 'due_date', 'return_date', 'status', 'overdue_fine']
        widgets = {
            'member': forms.Select(attrs={
                'class': 'form-select',
            }),
            'book': forms.Select(attrs={
                'class': 'form-select',
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'return_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'overdue_fine': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '罰款金額',
                'min': '0',
                'step': '0.01',
            }),
        }


class CreateBorrowForm(forms.Form):
    """
    建立借閱紀錄的表單
    用戶選擇會員和圖書，系統會自動驗證和建立紀錄
    """
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        label='會員',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        help_text='只能選擇正常狀態的會員'
    )
    book = forms.ModelChoiceField(
        queryset=Book.objects.filter(status='available'),
        label='圖書',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        help_text='只能選擇上架且有庫存的圖書'
    )

    def clean(self):
        """
        驗證表單數據
        """
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        book = cleaned_data.get('book')

        if member and book:
            # 檢查會員是否有未繳罰款
            if member.outstanding_fine > 0:
                raise forms.ValidationError(
                    f'會員有未繳罰款 NT$ {member.outstanding_fine}，請先清除罰款。'
                )

            # 檢查圖書庫存
            if book.available_quantity <= 0:
                raise forms.ValidationError(
                    f'圖書「{book.title}」暫無可借館藏。'
                )

        return cleaned_data


class ReturnBorrowForm(forms.Form):
    """
    還書搜尋的表單
    使用關鍵字搜尋會員名稱或書名
    """
    keyword = forms.CharField(
        label='關鍵字搜尋（會員名稱或書名）',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '輸入會員名稱或書名...',
        })
    )

    def clean(self):
        """
        驗證表單數據
        """
        cleaned_data = super().clean()
        keyword = cleaned_data.get('keyword', '').strip()
        
        if not keyword:
            raise forms.ValidationError('請輸入關鍵字（會員名稱或書名）。')
        
        return cleaned_data


class RegisterForm(forms.Form):
    """
    新會員註冊表單
    整合 User 帳號建立和 Member 個人資料
    """
    # User 相關欄位
    username = forms.CharField(
        label='帳號',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入帳號（用於登入，只能英文和數字）',
            'autocomplete': 'username',
        }),
        help_text='只能包含英文、數字和 @/./+/-/_ 符號'
    )
    
    email = forms.EmailField(
        label='電郵',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入電子郵件',
            'autocomplete': 'email',
        })
    )
    
    password1 = forms.CharField(
        label='密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入密碼（至少 8 個字元）',
            'autocomplete': 'new-password',
        })
    )
    
    password2 = forms.CharField(
        label='確認密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '再次輸入密碼以確認',
            'autocomplete': 'new-password',
        })
    )
    
    # Member 相關欄位
    first_name = forms.CharField(
        label='名字',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例如：小明',
        })
    )
    
    last_name = forms.CharField(
        label='姓氏',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例如：王',
        })
    )
    
    phone = forms.CharField(
        label='電話',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例如：0912-345-678',
        })
    )
    
    agree_terms = forms.BooleanField(
        label='我已閱讀並同意社群守則與隱私政策',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        required=True
    )
    
    def clean_username(self):
        """
        验证用户名是否已存在
        """
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('此帳號已被使用，請選擇其他帳號。')
        return username
    
    def clean_email(self):
        """
        验证电子邮件是否已存在
        """
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('此電郵已被使用，請選擇其他電郵。')
        return email
    
    def clean(self):
        """
        验证两个密码是否一致，并检查密码强度
        """
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('兩次輸入的密碼不一致，請重新輸入。')
            
            if len(password1) < 8:
                raise forms.ValidationError('密碼長度至少 8 個字元。')
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        同時建立 User 和 Member
        利用 transaction.atomic() 確保安全
        """
        from django.db import transaction
        
        with transaction.atomic():
            # 建立 User
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=self.cleaned_data['password1'],
                first_name=self.cleaned_data.get('first_name', ''),
                last_name=self.cleaned_data.get('last_name', ''),
            )
            
            # 建立 Member
            member = Member.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                status='active',
            )
        
        return user
