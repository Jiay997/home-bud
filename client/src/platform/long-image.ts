/**
 * 长图导出与保存的平台适配层（uni-app 跨端：微信小程序 + H5）。
 *
 * 两端能力差异：
 * - 小程序：`createSelectorQuery().fields({ node: true })` 取 canvas 2d 节点 →
 *   `canvasToTempFilePath` 导出临时文件 → `saveImageToPhotosAlbum` 存入系统相册；
 * - H5：`createSelectorQuery` 不支持 node 查询、canvasToTempFilePath 与相册 API 均未实现，
 *   故改用离屏 canvas 绘制 → `toDataURL` → `<a download>` 触发浏览器下载。
 *
 * 绘制与排版逻辑（layoutLongImage / renderLongImage / stripMarkdown）两端共用，
 * 仅「取画布」与「落盘」两步分叉，因此差异收敛在本模块内。
 */
import {
  layoutLongImage,
  renderLongImage,
  type LongImageCanvasContext,
  type LongImageDoc,
  type LongImageLayout
} from '../services/image-export'

/** 长图保存结果：saved = 已保存；denied = 权限被拒（仅小程序相册路径可能返回） */
export type LongImageSaveOutcome = 'saved' | 'denied'

/** 长图导出参数 */
export interface LongImageExportOptions {
  /** 长图内容文档 */
  doc: LongImageDoc
  /** 小程序端 canvas 选择器（H5 走离屏 canvas，无需该值） */
  selector?: string
  /** 小程序端组件实例（限定选择器作用域，避免跨页面串扰） */
  instance?: { proxy?: unknown } | null
}

/** 导出画布逻辑宽度（与设计稿一致） */
const EXPORT_CANVAS_WIDTH = 375

// #ifdef MP-WEIXIN
/**
 * 读取设备像素比，用于按分辨率放大导出图。
 * @returns 设备像素比；读取失败时回退 2
 */
function mpPixelRatio(): number {
  try {
    return uni.getSystemInfoSync().pixelRatio || 2
  } catch {
    return 2
  }
}

/**
 * 查询 canvas 2d 节点。
 * @param selector canvas 选择器
 * @param instance 组件实例；提供时限定查询作用域
 * @returns canvas 节点
 * @throws Error 节点未就绪时抛出（页面渲染异常或 canvas 未挂载）
 */
function mpQueryCanvasNode(
  selector: string,
  instance?: { proxy?: unknown } | null
): Promise<any> {
  return new Promise((resolve, reject) => {
    const query = uni.createSelectorQuery()
    const scoped = instance?.proxy ? query.in(instance.proxy as any) : query
    scoped
      .select(selector)
      .fields({ node: true, size: true } as any, (res: any) => {
        const node = Array.isArray(res) ? res[0]?.node : res?.node
        if (node) resolve(node)
        else reject(new Error('画布初始化失败'))
      })
      .exec()
  })
}

/**
 * 把 canvas 导出为本地临时文件。
 * @param canvas canvas 2d 节点
 * @param layout 排版结果（宽高用于导出尺寸）
 * @param dpr 设备像素比
 * @returns 本地临时文件路径
 * @throws Error 导出失败时抛出
 */
function mpCanvasToTempFile(canvas: any, layout: LongImageLayout, dpr: number): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.canvasToTempFilePath({
      canvas,
      x: 0,
      y: 0,
      width: layout.width,
      height: layout.height,
      destWidth: Math.ceil(layout.width * dpr),
      destHeight: Math.ceil(layout.height * dpr),
      fileType: 'png',
      success: (res: any) => resolve(res.tempFilePath),
      fail: () => reject(new Error('图片导出失败'))
    } as any)
  })
}

/**
 * 保存图片到系统相册。
 * @param filePath 本地文件路径
 * @returns saved = 已保存；denied = 用户拒绝相册权限
 * @throws Error 非权限类保存失败时抛出
 */
function mpSaveToAlbum(filePath: string): Promise<LongImageSaveOutcome> {
  return new Promise((resolve, reject) => {
    uni.saveImageToPhotosAlbum({
      filePath,
      success: () => resolve('saved'),
      fail: (error: any) => {
        const message = String(error?.errMsg || '')
        if (/auth|deny|authorize/i.test(message)) resolve('denied')
        else reject(new Error('保存失败'))
      }
    } as any)
  })
}

/**
 * 小程序端：绘制长图并保存到相册。
 * @param options 导出参数
 * @returns 保存结果
 * @throws Error 画布获取或导出失败时抛出
 */
async function mpRenderAndSave(options: LongImageExportOptions): Promise<LongImageSaveOutcome> {
  if (!options.selector) throw new Error('画布初始化失败')
  const canvas = await mpQueryCanvasNode(options.selector, options.instance)
  const ctx: any = canvas.getContext('2d')
  const dpr = mpPixelRatio()
  // 测量函数与画布上下文绑定：换行宽度必须按实际绘制字体计算
  const measure = (text: string, font: string) => {
    ctx.font = font
    return ctx.measureText(text).width
  }
  const layout = layoutLongImage(options.doc, { width: EXPORT_CANVAS_WIDTH, measure })
  canvas.width = Math.ceil(layout.width * dpr)
  canvas.height = Math.ceil(layout.height * dpr)
  if (typeof ctx.scale === 'function') ctx.scale(dpr, dpr)
  renderLongImage(ctx, layout)
  const filePath = await mpCanvasToTempFile(canvas, layout, dpr)
  return mpSaveToAlbum(filePath)
}
// #endif

// #ifdef H5
/**
 * H5 端：离屏 canvas 绘制长图并触发浏览器下载。
 * @param options 导出参数（selector/instance 在 H5 不参与）
 * @returns 固定返回 saved（浏览器下载无相册权限概念）
 * @throws Error 画布上下文创建失败时抛出
 */
async function h5RenderAndSave(options: LongImageExportOptions): Promise<LongImageSaveOutcome> {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('画布初始化失败')
  // 上限 3 倍避免超长图在低内存设备上导出失败
  const dpr = Math.min(3, Math.max(1, window.devicePixelRatio || 1))
  const measure = (text: string, font: string) => {
    ctx.font = font
    return ctx.measureText(text).width
  }
  const layout = layoutLongImage(options.doc, { width: EXPORT_CANVAS_WIDTH, measure })
  canvas.width = Math.ceil(layout.width * dpr)
  canvas.height = Math.ceil(layout.height * dpr)
  ctx.scale(dpr, dpr)
  // 浏览器 CanvasRenderingContext2D 的 fillStyle 类型比渲染器接口更宽（含渐变/图案），按契约断言
  renderLongImage(ctx as unknown as LongImageCanvasContext, layout)

  const link = document.createElement('a')
  link.href = canvas.toDataURL('image/png')
  // 文件名取报告标题并剔除文件系统非法字符
  link.download = `${options.doc.title || 'Babe宝伴'}.png`.replace(/[\\/:*?"<>|]/g, '_')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  return 'saved'
}
// #endif

/**
 * 绘制长图并落盘（按编译目标自动选择实现）。
 * @param options 导出参数
 * @returns 保存结果（H5 恒为 saved）
 * @throws Error 画布获取或导出失败时抛出（由调用方转用户提示）
 */
export function renderAndSaveLongImage(
  options: LongImageExportOptions
): Promise<LongImageSaveOutcome> {
  // #ifdef MP-WEIXIN
  return mpRenderAndSave(options)
  // #endif
  // #ifndef MP-WEIXIN
  return h5RenderAndSave(options)
  // #endif
}
