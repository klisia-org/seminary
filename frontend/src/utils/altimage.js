import SimpleImage from '@editorjs/simple-image'

/**
 * editorjs's simple-image has a caption and no alt field. The portal hides the
 * caption when the lesson is read, so here it *is* the alt text: the editor asks
 * for a description, and the rendered <img> carries it as `alt` (102 §7).
 */
export class AltImage extends SimpleImage {
	render() {
		const wrapper = super.render()
		const { image, caption } = this.nodes
		const syncAlt = () => image?.setAttribute('alt', (caption?.textContent || '').trim())
		syncAlt()
		if (caption && !this.readOnly) {
			caption.dataset.placeholder = __('Describe the image for students who can\'t see it')
			caption.setAttribute('aria-label', __('Image description (alt text)'))
			caption.addEventListener('input', syncAlt)
		}
		return wrapper
	}
}
