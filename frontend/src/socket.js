import { io } from 'socket.io-client'
import { socketio_port } from '../../../../sites/common_site_config.json'
import { getCachedListResource } from 'frappe-ui/src/resources/listResource'
import { getCachedResource } from 'frappe-ui/src/resources/resources'

export function initSocket() {
  let host = window.location.hostname;
  let protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  
  // Use the socketio_port if defined; otherwise, default to an empty string so that the URL uses the standard port.
  let port = socketio_port ? `:${socketio_port}` : '';
  
  // Explicitly use the /socket.io/ endpoint rather than /${siteName}
  let url = `${protocol}://${host}${port}/socket.io/`;
  
  let socket = io(url, {
    transports: ['websocket', 'polling'],
    withCredentials: true,
    reconnectionAttempts: 5,
  });
  
  console.log('Connecting to WebSocket:', url);
  
  socket.on('connect', () => {
    console.log('WebSocket connected');
  });
  
  socket.on('disconnect', (reason) => {
    console.warn('WebSocket disconnected:', reason);
  });
  
  socket.on('connect_error', (error) => {
    console.error('WebSocket connection failed:', error);
  });
  
  socket.on('refetch_resource', (data) => {
    if (data.cache_key) {
      let resource =
        getCachedResource(data.cache_key) ||
        getCachedListResource(data.cache_key);
      if (resource) {
        resource.reload();
      }
    }
  });
  
  return socket;
}
