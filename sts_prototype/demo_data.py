"""Synthetic data for connection checks, not accuracy validation."""
import math

def landmarks(p=0.,lean=0.):
    hip=(256,312-p*120); a=math.radians(lean); b=math.radians(90*p)
    shoulder=(hip[0]+100*math.sin(a),hip[1]-100*math.cos(a))
    knee=(hip[0]+100*math.cos(b),hip[1]+100*math.sin(b))
    ankle=(knee[0],knee[1]+100)
    pts=[dict(x=.5,y=.5,z=0.,visibility=1.) for _ in range(33)]
    for i,(x,y) in zip((11,23,25,27),(shoulder,hip,knee,ankle)):
        pts[i].update(x=x/640,y=y/480)
    return pts

def run_demo(client):
    def call(method,path,body=None):
        r=client.request(method,path,json=body);r.raise_for_status();return r.json()
    sid=call('POST','/sessions',{'width':640,'height':480,'input_source':'simulation'})['session_id'];t=0.
    def frames(n,p,lean=0):
        nonlocal t
        for i in range(n):
            progress=p(i/(n-1)) if callable(p) else p
            result=call('POST',f'/sessions/{sid}/frames',{'t':round(t,6),'landmarks':landmarks(progress,lean)})
            t+=.05
        return result
    call('POST',f'/sessions/{sid}/calibration',{'posture':'duduk','delay':0});frames(55,0)
    frames(45,1)
    call('POST',f'/sessions/{sid}/calibration',{'posture':'berdiri','delay':0});frames(55,1)
    frames(50,0);frames(20,0,28);frames(35,lambda p:p,28);frames(50,1)
    frames(35,lambda p:1-p);result=frames(45,0)
    return sid,result

if __name__=='__main__':
    import httpx
    with httpx.Client(base_url='http://127.0.0.1:8000') as client:
        sid,result=run_demo(client)
        print('SIMULASI:',result['complete'],'bangkit,',result['cycles'],'siklus')
        r=client.post(f'/sessions/{sid}/finish');r.raise_for_status()
        print('Hasil: http://127.0.0.1:8000/sessions/'+sid+'/export')
