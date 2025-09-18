const common_site_config = require('../../../sites/common_site_config.json');
const { webserver_port } = common_site_config;

interface ProxyTarget {
	target: string;
	ws: boolean;
	router: (req: Request) => string;
}

interface ProxyOptions {
	[key: string]: ProxyTarget;
}

interface Request {
	headers: {
		host: string;
	};
}

const proxyOptions: ProxyOptions = {
	'^/(app|api|assets|files|private)': {
		target: `http://127.0.0.1:${webserver_port}`,
		ws: true,
		router: function (req: Request): string {
			const site_name = req.headers.host.split(':')[0];
			return `http://${site_name}:${webserver_port}`;
		}
	}
};

export default proxyOptions;
