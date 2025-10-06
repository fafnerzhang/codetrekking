import pino from 'pino';

const isDevelopment = process.env.NODE_ENV === 'development';

// Simple console logger for development
class DevLogger {
  private logLevel: number;

  constructor(level = 'info') {
    const levels: Record<string, number> = {
      trace: 10, debug: 20, info: 30, warn: 40, error: 50, fatal: 60
    };
    this.logLevel = levels[level] || 30;
  }

  private shouldLog(level: number): boolean {
    return level >= this.logLevel;
  }

  private formatLog(level: string, msg: string, data?: any): void {
    const colors: Record<string, string> = {
      debug: '\x1b[36m',   // cyan
      info: '\x1b[32m',    // green
      warn: '\x1b[33m',    // yellow
      error: '\x1b[31m',   // red
      fatal: '\x1b[35m',   // magenta
    };

    const timestamp = new Date().toLocaleTimeString('zh-CN', {
      hour12: false,
      timeZone: 'Asia/Shanghai'
    });

    const color = colors[level] || '\x1b[37m';
    const reset = '\x1b[0m';

    console.log(`\x1b[90m[${timestamp}]${reset} ${color}${level.toUpperCase().padEnd(5)}${reset} ${msg}`);

    if (data && Object.keys(data).length > 0) {
      const cleanData = { ...data };
      delete cleanData.pid;
      delete cleanData.hostname;
      if (Object.keys(cleanData).length > 0) {
        console.log(`\x1b[90m    ${JSON.stringify(cleanData, null, 2).replace(/\n/g, '\n    ')}${reset}`);
      }
    }
  }

  debug(data: any, msg?: string): void {
    if (!this.shouldLog(20)) return;
    this.formatLog('debug', msg || data.msg || 'Debug message', typeof data === 'object' ? data : undefined);
  }

  info(data: any, msg?: string): void {
    if (!this.shouldLog(30)) return;
    this.formatLog('info', msg || data.msg || 'Info message', typeof data === 'object' ? data : undefined);
  }

  warn(data: any, msg?: string): void {
    if (!this.shouldLog(40)) return;
    this.formatLog('warn', msg || data.msg || 'Warning message', typeof data === 'object' ? data : undefined);
  }

  error(data: any, msg?: string): void {
    if (!this.shouldLog(50)) return;
    this.formatLog('error', msg || data.msg || 'Error message', typeof data === 'object' ? data : undefined);
  }

  fatal(data: any, msg?: string): void {
    if (!this.shouldLog(60)) return;
    this.formatLog('fatal', msg || data.msg || 'Fatal message', typeof data === 'object' ? data : undefined);
  }
}

export const logger = isDevelopment
  ? new DevLogger(process.env.LOG_LEVEL || 'debug')
  : pino({
      level: process.env.LOG_LEVEL || 'info',
      formatters: {
        level: (label) => ({ level: label }),
      },
      timestamp: pino.stdTimeFunctions.isoTime,
      serializers: {
        req: pino.stdSerializers.req,
        res: pino.stdSerializers.res,
        err: pino.stdSerializers.err,
      },
    });

export default logger;