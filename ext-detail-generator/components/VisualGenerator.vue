<template>
  <div class="visual-generator-sidebar" :class="{ 'collapsed': !showPanel }">
    <!-- Collapse/Expand Toggle -->
    <div class="sidebar-toggle" @click="showPanel = !showPanel">
      {{ showPanel ? '▶' : '◀' }}
    </div>

    <!-- Sidebar Content -->
    <div class="sidebar-content">
      <div class="panel-header">
        <span>AI 视觉助手</span>
      </div>

      <div class="panel-body">
        <!-- Step 1: Grabbing -->
        <div v-if="status === 'idle'" class="step-box">
          <p class="page-info">当前：{{ pageType }}</p>
          <button @click="handleGrab" class="action-btn">一键抓取商品</button>
        </div>

        <!-- Step 2: Review & Generate -->
        <div v-if="status === 'grabbed'" class="step-box">
          <div class="product-preview-vertical">
            <!-- Gallery Selector -->
            <div class="gallery-selector">
              <p class="section-title">选择主图 (橱窗图)</p>
              <div class="gallery-scroll">
                <div 
                  v-for="(img, idx) in productData.gallery_images" 
                  :key="idx" 
                  class="gallery-item"
                  :class="{ 'active': productData.image === img }"
                  @click="selectMainImage(img)"
                >
                  <img :src="img" />
                </div>
              </div>
            </div>

            <div class="main-preview">
              <p class="section-title">当前选定主图</p>
              <img :src="productData.image" class="preview-img-large" />
            </div>

            <!-- Detail Images Viewer -->
            <div class="gallery-selector mt-10">
              <p class="section-title">抓取到的详情图 ({{ productData.detail_images.length }}张)</p>
              <div v-if="productData.detail_images.length > 0" class="gallery-scroll">
                <div 
                  v-for="(img, idx) in productData.detail_images" 
                  :key="idx" 
                  class="gallery-item"
                  @click="selectMainImage(img)"
                >
                  <img :src="img" />
                </div>
              </div>
              <div v-else class="no-data-hint">
                未检测到详情图，请尝试手动向下滚动商品详情区域后再抓取
              </div>
              <p class="hint-text" v-if="productData.detail_images.length > 0">点击图片可将其设为主图</p>
            </div>

            <div class="info-vertical">
              <input v-model="productData.name" placeholder="商品名称" class="input-field" />
              <textarea v-model="productData.detail" placeholder="简要描述" class="textarea-field"></textarea>
              <textarea v-model="productData.attributes" placeholder="规格参数" class="textarea-field small-text" rows="4"></textarea>
              
              <div class="options-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="needWhiteBg" />
                  <span>生成白底图</span>
                </label>
              </div>
            </div>
          </div>
          <button v-if="needWhiteBg" @click="handleGenerateWhiteBg" :disabled="isGenerating" class="action-btn">
            {{ isGenerating ? '正在生成白底图...' : '第一步：生成白底图' }}
          </button>
          <button v-else @click="handleGenerate" :disabled="isGenerating" class="action-btn generate-btn">
            {{ isGenerating ? '生成中...' : '直接生成场景图' }}
          </button>
          <button @click="status = 'idle'" class="link-btn">重新抓取</button>
        </div>

        <!-- Step 2.5: White BG Review -->
        <div v-if="status === 'white_bg_review'" class="step-box">
          <div class="review-container">
            <p class="step-title">请确认白底图质量</p>
            <div class="compare-box">
              <div class="compare-item">
                <span>原图</span>
                <img :src="productData.image" class="preview-img-small" />
              </div>
              <div class="compare-item">
                <span>白底图</span>
                <img :src="whiteBgBase64 || getFullUrl(whiteBgUrl)" class="preview-img-large highlight" />
              </div>
            </div>
            <div class="review-actions" v-if="!isGenerating">
              <button @click="handleConfirmWhiteBg" class="action-btn confirm-btn">确认，生成场景图</button>
              <button @click="handleGenerateWhiteBg" :disabled="isGenerating" class="action-btn retry-btn">
                {{ isGenerating ? '重新生成中...' : '不合格，重新生成' }}
              </button>
            </div>
            <button @click="status = 'grabbed'" class="link-btn">返回修改信息</button>
          </div>
        </div>

        <!-- Step 3: Results -->
        <div v-if="status === 'completed' || status === 'failed'" class="step-box">
          <div v-if="status === 'failed'" class="error-msg">
            失败: {{ error }}
            <button @click="status = 'grabbed'" class="small-btn">重试</button>
          </div>
          
          <div v-if="status === 'completed'" class="results-list">
            <div v-for="(img, index) in resultImages" :key="index" class="result-item-vertical">
              <div class="image-wrapper">
                <img 
                  :src="resultImagesBase64[index] || getFullUrl(img)" 
                  class="result-img-full" 
                  @error="handleImageError($event, index)"
                />
                <div class="image-loading-overlay" v-if="loadingImages[index]">
                  <span>加载中...</span>
                </div>
              </div>
              <div class="result-actions">
                <a :href="getFullUrl(img)" target="_blank" class="download-link">查看原图</a>
                <span class="retry-load-btn" @click="reloadImage(index)">加载失败? 刷新</span>
              </div>
            </div>
          </div>
          <button @click="status = 'idle'" class="action-btn mt-10">继续生成</button>
        </div>

        <!-- Progress Overlay -->
        <div v-if="isGenerating" class="loading-overlay-inline">
          <div class="spinner"></div>
          <p>AI 正在生成...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const showPanel = ref(false);
const status = ref<'idle' | 'grabbed' | 'white_bg_review' | 'completed' | 'failed'>('idle');
const isGenerating = ref(false);
const needWhiteBg = ref(true);
const whiteBgUrl = ref('');
const whiteBgBase64 = ref('');
const error = ref('');
const resultImages = ref<string[]>([]);
const resultImagesBase64 = ref<string[]>([]);
const currentProductIndex = ref<number | null>(null);
const loadingImages = ref<boolean[]>([]);

// 图片加载错误处理
const handleImageError = (event: Event, index: number) => {
  const target = event.target as HTMLImageElement;
  console.warn(`[Visual Generator] Image load failed for index ${index}: ${target.src}`);
  // 如果 URL 加载失败，且有 Base64，尝试强制切回 Base64
  if (resultImagesBase64.value[index] && target.src !== resultImagesBase64.value[index]) {
    target.src = resultImagesBase64.value[index];
  }
};

// 手动刷新图片
const reloadImage = (index: number) => {
  const imgUrl = resultImages.value[index];
  if (!imgUrl) return;
  
  loadingImages.value[index] = true;
  const fullUrl = getFullUrl(imgUrl);
  
  // 添加随机参数强制绕过浏览器缓存
  const separator = fullUrl.includes('?') ? '&' : '?';
  const timestampedUrl = `${fullUrl}${separator}t=${Date.now()}`;
  
  // 查找对应的图片元素并更新
  const images = document.querySelectorAll('.result-img-full');
  if (images[index]) {
    (images[index] as HTMLImageElement).src = timestampedUrl;
    setTimeout(() => {
      loadingImages.value[index] = false;
    }, 1000);
  }
};
const pageType = ref('未知页面');

const productData = ref({
  name: '',
  detail: '',
  attributes: '',
  image: '',
  image_base64: '',
  gallery_images: [] as string[],
  detail_images: [] as string[]
});

const BACKEND_URL = 'http://localhost:8000';

onMounted(() => {
  pageType.value = '1688 详情页';
});

const getFullUrl = (path: string) => {
  if (path.startsWith('http')) return path;
  return `${BACKEND_URL}${path}`;
};

const handleGrab = async () => {
  try {
    const data = await grabProductInfo();
    productData.value = data;
    status.value = 'grabbed';
  } catch (e) {
    console.error('Grab error:', e);
    alert('抓取失败，请确保在 1688 商品详情页操作');
  }
};

const grabProductInfo = async () => {
  // 1. 标题
  const title = document.querySelector('.title-content h1')?.textContent?.trim() || 
                document.querySelector('.od-title h1')?.textContent?.trim() || 
                document.title;
  
  // 在抓取之前，先模拟滚动以触发 1688 的延迟加载和 Shadow DOM 渲染
  // 改进：采用分段式滚动，确保页面内容有时间加载
  const performSmoothScroll = async () => {
    const scrollStep = 800;
    const totalScroll = 4000; // 1688 详情页通常比较长
    const originalScrollPos = window.scrollY;

    for (let current = 0; current < totalScroll; current += scrollStep) {
      window.scrollBy(0, scrollStep);
      await new Promise(resolve => setTimeout(resolve, 150)); // 短暂等待加载
    }
    
    // 等待最后一段内容渲染
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 滚回原来的位置或顶部
    window.scrollTo(0, originalScrollPos);
  };

  await performSmoothScroll();

  const findDetailHost = () => {
    // 策略一：类名定位 (最稳定)
    let host = document.querySelector('.html-description');
    if (host) return host;

    // 策略二：标签前缀匹配 (DOM 中 tagName 通常是大写)
    const allElements = document.getElementsByTagName('*');
    for (let i = 0; i < allElements.length; i++) {
      if (allElements[i].tagName.toUpperCase().startsWith('V-DETAIL-')) {
        return allElements[i];
      }
    }
    return null;
  };

  const detailHost = findDetailHost();

  // 辅助函数：清洗 URL 获取高清图
  const cleanImageUrl = (url: string): string => {
    if (!url) return '';
    let cleaned = url.trim();
    if (cleaned.startsWith('//')) cleaned = 'https:' + cleaned;
    
    // 1. 处理 1688 常见的缩略图后缀 (如 .60x60.jpg, .400x400.jpg 等)
    cleaned = cleaned.replace(/\.\d+x\d+.*\.jpg$/, '.jpg');
    
    // 2. 处理您提到的 _b.jpg 后缀
    cleaned = cleaned.replace(/_b\.jpg$/, '.jpg');
    
    // 3. 处理 .webp 后缀
    // 1688 的 webp 通常是 .jpg_.webp 这种形式，直接替换为 .jpg
    if (cleaned.includes('.jpg_.webp')) {
      cleaned = cleaned.replace(/\.jpg_\.webp$/, '.jpg');
    } else if (cleaned.endsWith('.webp')) {
      cleaned = cleaned.replace(/\.webp$/, '.jpg');
    }

    // 4. 再次检查是否因为替换产生了重复后缀 (例如 .jpg.jpg)
    cleaned = cleaned.replace(/\.jpg\.jpg$/, '.jpg');
    
    return cleaned;
  };

  // 2. 抓取橱窗图 (Gallery Images) - 对应 //*[@id="gallery"]/div/div[1]/div/div
  let galleryUrls: string[] = [];
  const galleryContainer = document.querySelector('#gallery');
  if (galleryContainer) {
    // 寻找容器内的所有项
    const items = Array.from(galleryContainer.querySelectorAll('.tab-item, .item, [class*="item"]'));
    
    galleryUrls = items.map(item => {
      // 过滤掉包含视频标识的项
      const hasVideoIcon = item.querySelector('.video-icon, .play-icon, [class*="video"], [class*="play"]');
      const hasVideoTag = item.querySelector('video');
      if (hasVideoIcon || hasVideoTag) return '';

      const img = item.querySelector('img');
      if (!img) return '';

      const src = img.getAttribute('data-lazyload-src') || 
                  img.getAttribute('original-src') || 
                  img.getAttribute('src') || 
                  img.src;
      
      return cleanImageUrl(src);
    }).filter(url => url && url.startsWith('http') && !url.includes('spacer.gif') && !url.includes('video_play') && !url.includes('v-play'));
    
    // 如果上面的项级过滤没抓到（可能是结构不同），回退到直接抓取图片并过滤
    if (galleryUrls.length === 0) {
      const imgs = Array.from(galleryContainer.querySelectorAll('img'));
      galleryUrls = imgs.map(img => {
        // 检查图片父级是否包含视频标识
        const parent = img.parentElement;
        if (parent && (parent.querySelector('[class*="video"]') || parent.querySelector('[class*="play"]'))) {
          return '';
        }

        const src = img.getAttribute('data-lazyload-src') || 
                    img.getAttribute('original-src') || 
                    img.getAttribute('src') || 
                    img.src;
        
        return cleanImageUrl(src);
      }).filter(url => url && url.startsWith('http') && !url.includes('spacer.gif') && !url.includes('video_play') && !url.includes('v-play'));
    }

    // 去重
    galleryUrls = [...new Set(galleryUrls)];

    // 逻辑调整：如果有第5张图（通常是白底图），则将其排在第一位展示，方便用户快速选择
    if (galleryUrls.length >= 5) {
      const fifthImage = galleryUrls[4];
      const remainingImages = galleryUrls.filter((_, index) => index !== 4);
      galleryUrls = [fifthImage, ...remainingImages];
    }
  }

  // 3. 商品属性 (Attributes)
  let attributes = '';
  
  const grabAttributes = () => {
    // 尝试多种常见的 1688 属性选择器
    const attrContainers = [
      '.ant-descriptions', // 针对您提供的 AntD 结构
      '.offer-attr-list', 
      '.prop-list', 
      '[class*="pc-detail-property"]', 
      '[class*="attribute-container"]',
      '.mod-detail-attributes',
      '.desc-item-content',
      '#mod-detail-attributes'
    ];

    let foundContainer = null;
    for (const selector of attrContainers) {
      const el = document.querySelector(selector);
      if (el && el.innerText.length > 20) {
        foundContainer = el;
        break;
      }
    }

    let results: string[] = [];

    if (foundContainer) {
      // 方式 A: 针对 AntD 描述列表结构 (您提供的 HTML)
      const labels = Array.from(foundContainer.querySelectorAll('.ant-descriptions-item-label'));
      const contents = Array.from(foundContainer.querySelectorAll('.ant-descriptions-item-content'));
      
      if (labels.length > 0 && labels.length === contents.length) {
        for (let i = 0; i < labels.length; i++) {
          const label = labels[i].textContent?.trim().replace(/[:：]/g, '') || '';
          const value = contents[i].querySelector('.field-value')?.textContent?.trim() || 
                        contents[i].textContent?.trim() || '';
          if (label && value) {
            results.push(`${label}: ${value}`);
          }
        }
      }

      // 方式 B: 如果方式 A 没抓到，尝试通用的网格布局
      if (results.length === 0) {
        const items = Array.from(foundContainer.querySelectorAll('[class*="property-item"], [class*="attribute-item"], .offer-attr-item'));
        if (items.length > 0) {
          results = items.map(el => {
            const label = el.querySelector('[class*="item-name"], [class*="attr-name"], .offer-attr-item-name')?.textContent?.trim() || '';
            const value = el.querySelector('[class*="item-value"], [class*="attr-value"], .offer-attr-item-value')?.textContent?.trim() || '';
            return label && value ? `${label}: ${value}` : '';
          }).filter(Boolean);
        }
      }

      // 方式 B: 针对表格结构 (tr/td)
      if (results.length === 0) {
        const rows = Array.from(foundContainer.querySelectorAll('tr'));
        rows.forEach(row => {
          const cells = Array.from(row.querySelectorAll('td, th'));
          for (let i = 0; i < cells.length; i += 2) {
            const label = cells[i]?.textContent?.trim().replace(/[:：]/g, '') || '';
            const value = cells[i+1]?.textContent?.trim() || '';
            if (label && value && label.length < 20) {
              results.push(`${label}: ${value}`);
            }
          }
        });
      }
    }

    // 方式 C: 兜底方案 - 全局扫描所有可能的属性对
    if (results.length === 0) {
      const allItems = Array.from(document.querySelectorAll('.offer-attr-item, [class*="property-item"]'));
      results = allItems.map(el => {
        const label = el.querySelector('.offer-attr-item-name, [class*="name"]')?.textContent?.trim().replace(/[:：]/g, '') || '';
        const value = el.querySelector('.offer-attr-item-value, [class*="value"]')?.textContent?.trim() || '';
        return label && value ? `${label}: ${value}` : '';
      }).filter(Boolean);
    }

    return results.join('\n');
  };

  attributes = grabAttributes();

  // 如果第一次没抓到，尝试轻微滚动页面后再次尝试（1688 经常需要滚动激活）
  if (!attributes) {
    console.log('Attributes not found, trying to scroll...');
    window.scrollBy(0, 500);
    // 延迟一小会儿等渲染
    await new Promise(resolve => setTimeout(resolve, 300));
    attributes = grabAttributes();
    window.scrollBy(0, -500); // 滚回去
  }

  // 4. 详情图 (Detail Images) - 处理 Shadow DOM 和 Lazy Loading
  let detailImgUrls: string[] = [];
  
  const getDetailImagesFromContainer = (container: Element | ShadowRoot) => {
    const imgs = Array.from(container.querySelectorAll('img')).filter(img => {
      // 1. 过滤掉“店铺推荐”区域的图片
      const isRecommendation = img.closest('.sdmap-dynamic-offer-list, .desc-dynamic-module, .offer-list-wapper');
      if (isRecommendation) {
        const text = isRecommendation.textContent || '';
        if (text.includes('店铺推荐') || text.includes('更多推荐')) {
          return false;
        }
      }

      // 2. 过滤掉带有跳转性质的动态备份图 (通常是店铺推荐的另一种形式)
      if (img.classList.contains('dynamic-backup-img')) {
        return false;
      }
      
      // 3. 过滤掉 title 中包含“跳转到对应的商品页面”的图片
      const title = img.getAttribute('title') || '';
      if (title.includes('跳转到对应的商品页面')) {
        return false;
      }

      return true;
    });
    return imgs.map(img => {
      // 1. 优先读取 src，因为在 Shadow DOM 中渲染后 src 通常已填充
      let src = img.getAttribute('src') || (img as HTMLImageElement).src;
      
      // 2. 如果 src 是占位图或为空，再尝试各种延迟加载属性
      if (!src || src.includes('spacer.gif') || src.includes('pixel.gif') || src === location.href) {
        src = img.getAttribute('data-lazyload-src') || 
              img.getAttribute('data-lazy-src') ||
              img.getAttribute('original-src') || 
              img.getAttribute('data-original') ||
              img.getAttribute('data-src');
      }
      
      // 3. 兜底方案：扫描所有属性
      if (!src || src === '') {
        for (const attr of Array.from(img.attributes)) {
          const val = attr.value;
          if (val && (val.startsWith('http') || val.startsWith('//')) && 
              (val.includes('.jpg') || val.includes('.png') || val.includes('.webp'))) {
            src = val;
            break;
          }
        }
      }

      return cleanImageUrl(src);
    }).filter(url => url && url.startsWith('http') && !url.includes('spacer.gif') && !url.includes('pixel.gif'));
  };

  // 尝试从主文档找
  const detailContainer = document.querySelector('#detail');
  if (detailContainer) {
    detailImgUrls = getDetailImagesFromContainer(detailContainer);
  }

  // 如果没找到，或者找到的太少，尝试穿透动态标签名的 Shadow DOM
  if (detailImgUrls.length < 3) {
    console.log('Searching for images in dynamic Shadow DOM components...');
    
    // 使用之前找到的 detailHost
    if (detailHost && detailHost.shadowRoot) {
      console.log(`Found shadowRoot on ${detailHost.tagName}, exploring content...`);
      // 必须穿透 Shadow DOM
      const shadowDetail = detailHost.shadowRoot.querySelector('#detail') || detailHost.shadowRoot;
      const shadowImgs = getDetailImagesFromContainer(shadowDetail);
      console.log(`Found ${shadowImgs.length} images in Shadow DOM`);
      // 合并并去重
      detailImgUrls = [...new Set([...detailImgUrls, ...shadowImgs])];
    } else {
      console.log('No suitable shadowRoot container found');
    }
  }

  detailImgUrls = detailImgUrls.slice(0, 20);

  // 默认选中第一张橱窗图作为主图
  const initialMainImage = galleryUrls.length > 0 ? galleryUrls[0] : '';
  const base64 = initialMainImage ? await getBase64Image(initialMainImage) : '';

  return {
    name: title,
    detail: title,
    attributes: attributes,
    image: initialMainImage,
    image_base64: base64,
    gallery_images: galleryUrls,
    detail_images: detailImgUrls
  };
};

const selectMainImage = async (url: string) => {
  productData.value.image = url;
  isGenerating.value = true; // 显示加载状态
  try {
    productData.value.image_base64 = await getBase64Image(url);
  } catch (e) {
    console.error('Failed to convert selected image to base64', e);
  } finally {
    isGenerating.value = false;
  }
};

const getBase64Image = (url: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx?.drawImage(img, 0, 0);
      resolve(canvas.toDataURL('image/jpeg'));
    };
    img.onerror = reject;
    img.src = url;
  });
};

const urlToBase64 = async (url: string): Promise<string> => {
  const resp = await fetch(url);
  const blob = await resp.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

const handleGenerateWhiteBg = async () => {
  isGenerating.value = true;
  error.value = '';
  
  try {
    const response = await browser.runtime.sendMessage({
      type: 'API_REQUEST',
      url: `${BACKEND_URL}/api/generate`,
      options: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: productData.value.name,
          detail: productData.value.detail,
          attributes: productData.value.attributes,
          image_base64: productData.value.image_base64,
          gallery_images: productData.value.gallery_images,
          detail_images: productData.value.detail_images,
          white_bg_only: true,
          save_to_data: true, // 第一步就存入正式目录，确保存储一致
          product_index: currentProductIndex.value // 如果重试，复用同一个序号
        })
      }
    });

    if (!response.success) throw new Error(response.error);
    const { task_id } = response.data;
    
    // 轮询直到完成
    const result = await pollTaskInternal(task_id);
    if (result && result.images.length > 0) {
      whiteBgUrl.value = result.images[0];
      whiteBgBase64.value = result.white_bg_base64 || '';
      if (result.product_index) {
        currentProductIndex.value = result.product_index;
      }
      status.value = 'white_bg_review';
    }
  } catch (e: any) {
    status.value = 'failed';
    error.value = e.message;
  } finally {
    isGenerating.value = false;
  }
};

const handleConfirmWhiteBg = async () => {
  // 确认后，直接调用 handleGenerate，使用已生成的 whiteBgUrl (服务器路径)
  handleGenerate(true);
};

const handleGenerate = async (useWhiteBg = false) => {
  isGenerating.value = true;
  error.value = '';
  
  try {
    const body: any = {
      name: productData.value.name,
      detail: productData.value.detail,
      attributes: productData.value.attributes,
      gallery_images: productData.value.gallery_images,
      detail_images: productData.value.detail_images,
      need_white_bg: false,
      save_to_data: true,
      product_index: currentProductIndex.value // 复用第一步创建的目录序号
    };

    if (useWhiteBg && whiteBgUrl.value) {
      // 直接传服务器端的相对路径，避免 Mixed Content (https 调 http) 的 fetch 失败
      body.image_path = whiteBgUrl.value;
    } else {
      body.image_base64 = productData.value.image_base64;
    }

    const response = await browser.runtime.sendMessage({
      type: 'API_REQUEST',
      url: `${BACKEND_URL}/api/generate`,
      options: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }
    });

    if (!response.success) throw new Error(response.error);
    const { task_id } = response.data;
    await pollTask(task_id);
    
  } catch (e: any) {
    status.value = 'failed';
    error.value = e.message;
  } finally {
    isGenerating.value = false;
  }
};

const pollTaskInternal = async (taskId: string): Promise<{images: string[], white_bg_base64?: string, images_base64?: string[], product_index?: number} | null> => {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      const response = await browser.runtime.sendMessage({
        type: 'API_REQUEST',
        url: `${BACKEND_URL}/api/task/${taskId}`,
        options: { method: 'GET' }
      });
      
      if (!response.success) {
        clearInterval(timer);
        reject(new Error(response.error));
        return;
      }

      const data = response.data;
      if (data.status === 'completed') {
        clearInterval(timer);
        resolve({
          images: data.images,
          white_bg_base64: data.white_bg_base64,
          images_base64: data.images_base64,
          product_index: data.product_index
        });
      } else if (data.status === 'failed') {
        clearInterval(timer);
        reject(new Error(data.error || '生成失败'));
      }
    }, 2000);
  });
};

const pollTask = async (taskId: string) => {
  try {
    const result = await pollTaskInternal(taskId);
    if (result) {
      resultImages.value = result.images;
      resultImagesBase64.value = result.images_base64 || [];
      if (result.product_index) {
        currentProductIndex.value = result.product_index;
      }
      status.value = 'completed';
    }
  } catch (e: any) {
    error.value = e.message;
    status.value = 'failed';
  }
};
</script>

<style scoped>
.visual-generator-sidebar {
  position: fixed;
  right: 0;
  top: 0;
  height: 100vh;
  width: 450px;
  background: white;
  box-shadow: -2px 0 12px rgba(0,0,0,0.1);
  z-index: 999999;
  transition: transform 0.3s ease;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex;
  flex-direction: column;
}

.visual-generator-sidebar.collapsed {
  transform: translateX(450px);
}

.sidebar-toggle {
  position: absolute;
  left: -30px;
  top: 50%;
  transform: translateY(-50%);
  width: 30px;
  height: 60px;
  background: #1890ff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 8px 0 0 8px;
  box-shadow: -2px 0 8px rgba(0,0,0,0.1);
  font-size: 12px;
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
  font-weight: bold;
  font-size: 16px;
  color: #333;
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.step-box {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-info {
  font-size: 13px;
  color: #666;
  background: #f0f2f5;
  padding: 8px; 
  border-radius: 4px;
}

.action-btn {
  background: #1890ff;
  color: white;
  border: none;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #40a9ff;
}

.generate-btn {
  background: #52c41a;
}

.generate-btn:hover {
  background: #73d13d;
}

.product-preview-vertical {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: bold;
  color: #666;
  margin-bottom: 8px;
}

.gallery-selector {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 8px;
}

.gallery-scroll {
  display: grid;
  grid-template-rows: repeat(2, 80px);
  grid-auto-flow: column;
  grid-auto-columns: 80px;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.gallery-scroll::-webkit-scrollbar {
  height: 4px;
}

.gallery-scroll::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 2px;
}

.gallery-item {
  width: 80px;
  height: 80px;
  border-radius: 4px;
  border: 2px solid transparent;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  box-sizing: border-box;
}

.gallery-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gallery-item.active {
  border-color: #1890ff;
  box-shadow: 0 0 4px rgba(24, 144, 255, 0.3);
}

.preview-img-large {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #eee;
}

.info-vertical {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-field, .textarea-field {
  width: 100%;
  padding: 10px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.input-field:focus, .textarea-field:focus {
  border-color: #1890ff;
  outline: none;
}

.textarea-field {
  min-height: 80px;
  resize: vertical;
}

.small-text {
  font-size: 12px;
  color: #666;
  background: #fafafa;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #444;
  cursor: pointer;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item-vertical {
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}

.result-img-full {
  width: 100%;
  display: block;
  border-radius: 4px;
}

.image-wrapper {
  position: relative;
  width: 100%;
  min-height: 200px;
  background: #f5f5f5;
  border-radius: 4px;
  overflow: hidden;
}

.image-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255,255,255,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #1890ff;
}

.result-actions {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8f9fa;
  border-radius: 0 0 4px 4px;
}

.retry-load-btn {
  font-size: 12px;
  color: #ff4d4f;
  cursor: pointer;
  text-decoration: underline;
}

.retry-load-btn:hover {
  color: #ff7875;
}

.download-link {
  color: #1890ff;
  text-decoration: none;
  font-size: 13px;
}

.loading-overlay-inline {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(255,255,255,0.8);
}

.spinner {
  width: 30px;
  height: 30px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #1890ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.link-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
}

.step-title {
  font-weight: bold;
  font-size: 15px;
  color: #333;
  margin-bottom: 8px;
}

.compare-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
}

.compare-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.compare-item span {
  font-size: 12px;
  color: #999;
}

.preview-img-small {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #eee;
}

.highlight {
  border: 2px solid #1890ff !important;
  box-shadow: 0 0 8px rgba(24, 144, 255, 0.2);
}

.review-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.confirm-btn {
  background: #52c41a;
}

.confirm-btn:hover {
  background: #73d13d;
}

.retry-btn {
  background: #faad14;
}

.retry-btn:hover {
  background: #ffc53d;
}

.no-data-hint {
  font-size: 12px;
  color: #ff4d4f;
  padding: 10px;
  background: #fff2f0;
  border: 1px border #ffccc7;
  border-radius: 4px;
  margin: 5px 0;
}

.hint-text {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

.mt-10 {
  margin-top: 10px;
}
</style>
