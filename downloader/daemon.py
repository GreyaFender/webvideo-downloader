# -*- coding:utf-8 -*-
import json
import threading
import queue
from dispatcher import TaskDispatcher
import config
import tools
from tools import WebServer, CLIENT_CLOSE_EXCEPTION


# 守护模式下的后台服务器
class DownloadServer(WebServer):
    ESTABLISHED = 0
    IN_TRANSIT = 1
    DATA_CACHE_SIZE = 10

    # 等待下载的任务队列
    taskQueue = queue.Queue()


    # 处理http请求
    def do_POST(self, client):
        try:
            body = client.rfile.read(int(client.headers['Content-Length']))
            task = json.loads(body.decode('utf-8'))
            self.printWithoutData(task)
            self.taskQueue.put(task)
            tools.normalResponse(client, "success")
        except Exception as e:
            tools.normalResponse(client, "failed")

    def new_client(self, client):
        client.status = self.ESTABLISHED

    # 处理websocket请求
    def message_received(self, client, msg):
        try:
            if client.status == self.ESTABLISHED:
                task = json.loads(msg.decode('utf-8'))
                self.taskQueue.put(task)
                client.task = task
                self.printWithoutData(task)

                if task['type'] == 'stream':
                    client.status = self.IN_TRANSIT
                    task['close'] = lambda : self.close(client)
                    task['dataQueue'] = queue.Queue(self.DATA_CACHE_SIZE)
                    for i in range(self.DATA_CACHE_SIZE):
                        task['dataQueue'].put(None)

            elif client.status == self.IN_TRANSIT:
                desc, chunk = msg.split(b'\r\n', 1)
                data = json.loads(desc.decode('utf-8'))
                data['chunk'] = chunk
                client.task['dataQueue'].put(data)

            self.send_message(client, 'success')
        except:
            self.send_message(client, 'failed')

    def client_left(self, client):
        if client.task and client.task.get('type') == 'stream':
            client.task['dataQueue'].put(CLIENT_CLOSE_EXCEPTION)

    def printWithoutData(self, task):
        copyTask = {key: task[key] for key in task}
        if copyTask.get('data'):
            copyTask['data'] = '...'
        print('\nReceive: %s\n' % tools.stringify(copyTask))


class Runner:
    def __init__(self):
        self.taskDispatcher = TaskDispatcher()

    def start(self):
        if config.interactive:
            self.startInteractive()
        else:
            self.startDaemon(config.port)

    # 交互模式，接受用户输入
    def startInteractive(self):
        while True:
            try:
                url = input('输入暴力猴链接或本地m3u8路径: ').strip()
                fileName = input('输入文件名: ').strip()
                isMultiPart = url.find('www.bilibili.com') != -1
                pRange = input('输入首、尾P(空格分隔)或单P: ').strip() if isMultiPart else None
            except KeyboardInterrupt:
                break

            self.taskDispatcher.dispatch(url=url, fileName=fileName, pRange=pRange)

    # 守护模式，监听web请求
    def startDaemon(self, port):
        # 消费者
        t = threading.Thread(target=self._downloadThread, daemon=True)
        t.start()

        # 生产者
        server = DownloadServer(port)
        while True:
            try:
                print("Listening on port %d for clients..." % port)
                server.serve_forever()
            except KeyboardInterrupt:
                if self.taskDispatcher.task:
                    self.taskDispatcher.shutdown()
                else:
                    break

    def _downloadThread(self):
        while True:
            task = DownloadServer.taskQueue.get()
            print('Handle: "%s"' % task['fileName'])
            self.taskDispatcher.dispatch(**task)
# For Only WeTV Global (Subtitle changed from webvtt to srt, just remove webvtt header)
# Just Remove webvtt header until "1"
def vtt_to_srt(self, vttFile):
    myFile = open(vttFile, 'r')
    vttfile = myFile.readlines()
    myFile.close()

    for i in range(0,15):
        if ( vttfile[i].startswith('1') ):
            break
        vttfile[i]=''

    srtFileName = vttFile.replace(".vtt",".srt")
    srtFile = open(srtFileName, 'a')
    srtFile.writelines(vttfile)
    srtFile.close()

def handleSubtitles(self, subtitles, fileName, videoName, headers = {}):
    print("-- dispatcher/handleSubtitles")
    subtitleUrls, subtitleNames = [], []
    subtitlesInfo = []
    # For WeTV subtitle file process ( .vtt to .srt )
    subtitleNames1, subtitlesInfo1 = [], []

    for name, url in subtitles:
        # remove .m3u8 from subtitle url
        url = url.replace(".m3u8","")
        subtitleUrls.append(url)
        subtitleName = tools.join(self.tempFilePath, '%s_%s%s' % \
            (fileName, name, tools.getSuffix(url)))
        subtitleNames1.append(subtitleName)
        subtitlesInfo1.append((name, subtitleName))

    self.downloader.downloadAll(subtitleUrls, subtitleNames1, headers, self.hlsThreadCnt)

    for each in subtitleNames1:
        # IF subtitle name is .vtt (This is WeTV)
        if ( ".vtt" in each ):
            # Convert vtt to srt
            self.vtt_to_srt(each)
            # subtitle name extension change from vtt to srt
            each = each.replace(".vtt",".srt")
            subtitleNames.append(each)
            tools.tryFixSrtFile(each)
            # for delete vtt file
            each = each.replace(".srt",".vtt")
            os.remove(each)
        else:
            subtitleNames.append(each)
            tools.tryFixSrtFile(each)

    for name1, each1 in subtitlesInfo1:
        # IF subtitle name is .vtt (This is WeTV)
        if ( ".vtt" in each1 ):
            # subtitle name extension change from vtt to srt
            each1 = each1.replace(".vtt",".srt")
        subtitlesInfo.append((name1, each1))

    targetFileName = tools.integrateSubtitles(subtitlesInfo, videoName)
    self.saveTempFile or tools.removeFiles(subtitleNames)
    return targetFileName


if __name__ == '__main__':
    runner = Runner()
    runner.start()
