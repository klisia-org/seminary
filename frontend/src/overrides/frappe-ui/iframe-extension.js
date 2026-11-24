// frappe-ui's iframe node, replaced (decision 109 §1, §4): see utils/richEditorNodes.js.
export { RichEmbed as IframeExtension, RichEmbed as default } from '../../utils/richEditorNodes.js'
export {
	detectPlatform,
	calculateAspectRatio,
	getOptimalDimensions,
	validateURL,
	processURL,
	ALLOWED_DOMAINS,
} from '../../../node_modules/frappe-ui/src/components/TextEditor/extensions/iframe/utils'
