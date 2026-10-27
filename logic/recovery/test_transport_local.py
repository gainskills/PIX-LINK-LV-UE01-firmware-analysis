"""Local TCP fixture only; never connects to the AP."""
import contextlib,socket,threading,time,unittest
from unittest.mock import patch
import flash_backup as fb

class LocalTransportTests(unittest.TestCase):
    def test_split_response_arrives_without_stdin_eof(self):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(4)
        port=listener.getsockname()[1];errors=[]
        def server():
            try:
                with listener.accept()[0] as conn:
                    conn.settimeout(4)
                    f=conn.makefile('rb')
                    conn.sendall(b'Login as:');self.assertEqual(f.readline(),b'admin\n')
                    conn.sendall(b'Password:');self.assertEqual(f.readline(),b'admin\n')
                    conn.sendall(b'OS>')
                    for index in range(2):
                        self.assertEqual(f.readline(),b'spi rd 0 16\n')
                        conn.sendall(b'11223344 ');time.sleep(.1)
                        conn.sendall(b'55667788 99aabbcc ddeeff00 \r\n\r\nOS>185, flush one!\n')
                    f.close()
            except BaseException as exc:errors.append(exc)
        thread=threading.Thread(target=server,daemon=True);thread.start()
        original=fb.subprocess.Popen
        def local(argv,*args,**kwargs):
            if argv[0]=='/usr/bin/curl':
                self.assertEqual(argv[-1],'telnet://192.168.1.2:23')
                argv=argv[:-1]+[f'telnet://127.0.0.1:{port}']
            else:
                self.assertEqual(argv[0],'/usr/bin/nc');self.assertEqual(argv[-2:],['192.168.1.2','23'])
                argv=argv[:-2]+['127.0.0.1',str(port)]
            return original(argv,*args,**kwargs)
        try:
            with patch.object(fb.subprocess,'Popen',local):
                with fb.Session() as session:
                    for _ in range(2):
                        raw=session.read(0,16)
                        self.assertEqual(fb.parse_read(raw,16),bytes.fromhex('4433221188776655ccbbaa9900ffeedd'))
                        self.assertFalse(session.p.stdin.closed)
        finally:
            listener.close();thread.join(timeout=5)
        if errors:raise errors[0]
if __name__=='__main__':unittest.main(verbosity=2)
