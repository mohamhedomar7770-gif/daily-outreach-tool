# أداة Outreach اليومية

بتجهزلك كل يوم رسايل outreach مخصصة للبراندات اللي في data/brands.csv، جاهزة للنسخ من صفحة ويب.

## خطوات الإعداد (مرة واحدة بس)

1. اعمل حساب على GitHub (مجاني)، وارفع الملفات دي كـ repository جديد بنفس المسارات.
2. جيب Anthropic API Key من console.anthropic.com، وضيفه في Settings → Secrets and variables → Actions باسم ANTHROPIC_API_KEY.
3. فعّل GitHub Pages: Settings → Pages → Branch: main، الفولدر: /docs.
4. حدّث data/brands.csv بالبراندات الحقيقية بدل صفوف المثال.
5. شغّل الأداة أول مرة يدوي من تاب Actions → Daily Outreach Generator → Run workflow.
6. بعد كده هتشتغل لوحدها كل يوم الساعة 8 الصبح بتوقيت مصر.

## فحص الإعلانات الحقيقي (اختياري لاحقًا)
لازم Access Token من developers.facebook.com (Ads Library API، محتاج ID verification)، يتضاف كـ secret باسم META_ACCESS_TOKEN.