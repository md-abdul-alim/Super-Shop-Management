from django.db import models
from django.conf import settings
from django.shortcuts import reverse
from django.db.models.signals import post_save
from django.db.models import Sum
import qrcode
import uuid
from io import BytesIO
from django.core.files import File
from PIL import Image, ImageDraw
# Create your models here.


# userprofile for payment part
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    one_click_purchasing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


def userprofile_receiver(sender, instance, created, *args, **kwargs):

    # ignore if this is an existing User
    # if not created:
    #     return
    # UserProfile.objects.create(user=instance)
    if created:
        userprofile = UserProfile.objects.create(user=instance)

post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)

ADDRESS_CHOICES = (
    ('B', 'Billing'),
    ('S', 'Shipping')
)


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    street_address = models.CharField(max_length=100)
    apartment_address = models.CharField(max_length=100)
    # install all countries https://github.com/SmileyChris/django-countries
    # https://github.com/SmileyChris/django-countries#installation
    country = models.CharField(max_length=100, default='Bangladesh')
    zip = models.CharField(max_length=100)
    address_type = models.CharField(max_length=1, choices=ADDRESS_CHOICES)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name_plural = 'Addresses'


class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class Coupon(models.Model):
    code = models.CharField(max_length=15)
    # minus coupon amount
    amount = models.FloatField()

    def __str__(self):
        return self.code


CATEGORY_CHOICES = (
    ('Ow', 'Outwear'),
    ('P', 'Pant'),
    ('S', 'Shirt'),
    ('SW', 'Sport wear'),
    ('W', 'Watch'),
    ('Fr', 'Fruit'),
    ('C', 'Chocolet'),
    ('Fo', 'Food')

)
LABEL_CHOICES = (
    ('D', 'danger'),
    ('P', 'primary'),
    ('S', 'secondary')

)


class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.FloatField()
    discount_price = models.FloatField(blank=True, null=True)
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=2)
    label = models.CharField(choices=LABEL_CHOICES, max_length=1)
    slug = models.SlugField()
    description = models.TextField()
    # image=models.ImageField(blank=True,null=True) #extra add korar smy blank null true kore dibo
    image = models.ImageField()
    current_stock = models.IntegerField(default=1)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("ecommerce:product", kwargs={"slug": self.slug})

    def get_add_to_cart_url(self):
        return reverse("ecommerce:add-to-cart", kwargs={"slug": self.slug})

    def get_remove_from_cart_url(self):
        return reverse("ecommerce:remove-from-cart", kwargs={"slug": self.slug})


class OrderItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} of {self.item.title}"
    # for showing detain in table about price

    def get_total_item_price(self):
        return self.quantity * self.item.price

    def get_total_discount_item_price(self):
        return self.quantity * self.item.discount_price

    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_discount_item_price()

    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_discount_item_price()
        return self.get_total_item_price()


class Order(models.Model):
    # https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#referencing-the-user-model
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ref_code = models.CharField(max_length=20)
    items = models.ManyToManyField(OrderItem)
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField()
    ordered = models.BooleanField(default=False)
    billing_address = models.ForeignKey(
        'Address', related_name='billing_address', on_delete=models.SET_NULL, blank=True, null=True)
    shipping_address = models.ForeignKey(
        'Address', related_name='shipping_address', on_delete=models.SET_NULL, blank=True, null=True)
    payment = models.ForeignKey(
        'Payment', on_delete=models.SET_NULL, blank=True, null=True)
    coupon = models.ForeignKey(
        'Coupon', on_delete=models.SET_NULL, blank=True, null=True)
    being_delivered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    refund_requested = models.BooleanField(default=False)
    refund_granted = models.BooleanField(default=False)
    qr_invoice = models.ImageField(upload_to = 'qr_codes', blank=True)

    '''
    1. Item added to cart
    2. Adding a billing address
    (Failed checkout)
    3. Payment
    (Preprocessing, Processing, packaging etc.)
    4. Being delivered
    5. Received
    6. Refunds
    '''

    def __str__(self):
        return self.user.username

    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        if self.coupon:
            total -= self.coupon.amount
        return total

    def qr_code_invoice(self, *args, **kwargs):
        qr = qrcode.QRCode(
            version=5, # Control image size
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5, # Control image size
            border=3, # This control the outside padding of the image
        )
        qr_code_data = f'Customer Name: {self.user.username}, Order Ref Code: {self.ref_code}'
        qr.add_data(qr_code_data)
        qr.make(fit=False) # fit False stop system to fix image size it own.This is shortcut way. For advance control use [image_factory]
        img = qr.make_image(fill_color="black", back_color="white")
        # file_name = f'qr_code - {self.name}.png'
        file_name = 'qr-' + str(uuid.uuid4()) + '.png'
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        self.qr_invoice.save(file_name, File(buffer), save = False)
        img.close()
        super().save(*args, **kwargs)

    def get_image_url(self):
        return reverse("ecommerce:qr-download", kwargs={"url": self.qr_invoice})


class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.CharField(max_length=200)
    accepted = models.BooleanField(default=False)
    email = models.EmailField()

    def __str__(self):
        return f"{self.pk}"

class QrCode(models.Model):
    name = models.CharField(max_length=255)
    qr_code = models.ImageField(upload_to = 'qr_codes', blank=True)

    def __str__(self):
        return str(self.name)

    '''
        https://pypi.org/project/qrcode/
    '''
    def save(self, *args, **kwargs):
        qr = qrcode.QRCode(
            version=5, # Control image size
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5, # Control image size
            border=3, # This control the outside padding of the image
        )
        qr.add_data(self.name)
        qr.make(fit=False) # fit False stop system to fix image size it own.This is shortcut way. For advance control use [image_factory]
        img = qr.make_image(fill_color="black", back_color="white")
        # file_name = f'qr_code - {self.name}.png'
        file_name = 'qr-' + str(uuid.uuid4()) + '.png'
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        self.qr_code.save(file_name, File(buffer), save = False)
        img.close()
        super().save(*args, **kwargs)
