# ADHD Coding Skill

**Daha anlaşılır kodlama sohbetleri. Rehberlik istediğinde tek net adım; işi devrettiğinde tamamlanmış sonuç.**

[English](README.md) · [Skill talimatları](skills/adhd-coding/SKILL.md) · [Davranış senaryoları](tests/scenarios.md)

Kodlama asistanıyla ADHD'ye uygun çalışmayı destekleyen, yalnızca talimatlardan oluşan bir Agent Skill. Açıklamaları yönetilebilir tutmayı, aradan sonra göreve dönmeyi ve yeni fikirlerin mevcut işi dağıtmasını azaltmayı amaçlar. Bu iletişim tercihlerini kullanmak için ADHD tanısı gerekmez.

## Nasıl davranır?

- **İşi yaparken:** İzin verilmiş işi tamamlar ve sonucu kısa aktarır.
- **Rehberlik ederken:** Görünür bir tamamlanma koşulu olan tek somut adım verir.
- **Açıklarken:** İstediğin ayrıntı düzeyini ve kod örneklerini korur.

Kısa yanıt varsayılandır. İstediğin an "ayrıntılı anlat", "planın tamamını göster" veya "bu tarzı bırak" diyebilirsin.

## Codex'e kurulum

1. Bu repoyu indir veya klonla.
2. Skill'i kullanacağın projede gerekirse `.agents/skills` klasörünü oluştur.
3. Bu repodaki `skills/adhd-coding` klasörünü oraya kopyala. Son konum `.agents/skills/adhd-coding/SKILL.md` olmalı. Hedef klasör zaten varsa üzerine yazmadan önce sürümleri karşılaştır ve kendi değişikliklerini koru.
4. Kodlama sohbetinde çağır:

```text
$adhd-coding Giriş formunu bitirmeme yardım et. Kısa güncellemeler ver, uygulamayı ve testleri sen yap.
```

Codex, proje skill'lerini `.agents/skills`, kullanıcı skill'lerini `~/.agents/skills` altında destekler. Tüm projelerde kullanmak için aynı klasörü kullanıcı konumuna kopyalayabilirsin. Güncel keşif ve kurulum davranışı için [resmî skill belgesine](https://learn.chatgpt.com/docs/build-skills) bak. Skill görünmezse Codex'i yeniden başlat.

Başka bir Agent Skills destekli kodlama asistanında aynı skill klasörünü, o ürünün kurulum talimatlarına göre kullan. Her ürünün test edildiği iddia edilmez. `agents/openai.yaml`, isteğe bağlı Codex metaverisini içerir.

## Proje çalışma hafızası

Devam eden proje işlerinde skill, hedef projenin `WORKING_MEMORY.md` dosyasında tek ve kısa bir metin tutar; proje kuralları eşdeğer bir devir dosyası belirtiyorsa onu kullanır. Anlamlı aşamalarda veya oturum devrinde hedefi, doğrulanmış durumu, kararları, değişen dosya yollarını, tarihli test sonuçlarını, engelleri, ertelenen fikirleri ve sıradaki adımı kaydeder. Devam ederken kaydı okur ve mevcut dosyaları kontrol eder; geçmiş sonuçları yeni doğrulama gibi sunmaz. Diğer skill'lerin plan ve raporlarına yollarıyla atıf yapar; iş akışlarını, kontrollerini ve izinlerini korur. Tekil sorular veya salt okunur işler için hafıza oluşturmaz; istediğinde hafıza güncellemelerini durdurabilirsin. Dosya araçları ve yazma izni gerekir; kaydın bulunması, sonraki oturumda skill'in otomatik yükleneceğini garanti etmez. RAG, harici servis veya çalışma zamanı bağımlılığı eklenmez. [Çalışma hafızası kabul senaryolarına](tests/scenarios.md#working-memory-and-skill-compatibility) bak.

## Deneme istekleri

```text
$adhd-coding React öğrenmek istiyorum ama başlayamıyorum. Bana tek somut ilk adım ver.
```

```text
$adhd-coding Nerede kaldığımızı unuttum. Son doğrulanmış durumu kısaca özetle ve mevcut göreve dön.
```

```text
$adhd-coding Bu hatayı düzelt, ilgili testleri çalıştır ve sonucu kısa yaz. Yalnızca gerekli bilgi eksikse soru sor.
```

Skill kendiliğinden zamanlayıcı başlatmaz, kişisel sağlık bilgisi kaydetmez veya arka planda görev çalıştırmaz. Bunlar ayrı istek ve uygun araçlar gerektirir. Klinik etkinlik iddiası taşımayan bir iletişim desteğidir.

## Kontroller ve katkı

[Senaryolar](tests/scenarios.md) ve [değerlendirme kaydı](tests/evaluation.md), hangi davranışların kontrol edildiğini ve testlerin sınırlarını açıklar. Ayrıntılı istekleri yerine getirme ve izin verilmiş işi tamamlama da kapsama dahildir. Sonuçlar tıbbi kanıt veya her modelde aynı davranışın garantisi değildir.

Çevrim dışı kontroller:

```bash
python3 tests/validate_package.py
```

Canlı karşılaştırma (S1–S10; JSON sonuçları git dışı `work/` altına yazılır):

```bash
python3 tests/live_eval.py
python3 tests/live_eval.py --scenarios S1,S2,S3
```

İyileştirme önerirken kullanıcı isteğini, gözlenen yanıtı ve beklediğin davranışı yaz. Kurgusal veya anonimleştirilmiş örnekler kullan. Değişiklikleri kodlama iş birliğine odakla ve etkilenen senaryoları tekrar dene.

[MIT Lisansı](LICENSE).
