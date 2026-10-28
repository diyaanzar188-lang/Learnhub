from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ROOT=Path(r'C:\Users\ASUS\Pictures\Screenshots\Elearning')
FONT=Path(r'C:\Windows\Fonts')
S=2
REG=ImageFont.truetype(str(FONT/'times.ttf'),16*S)
ITAL=ImageFont.truetype(str(FONT/'timesi.ttf'),16*S)
BOLD=ImageFont.truetype(str(FONT/'timesbd.ttf'),20*S)
BODY=ImageFont.truetype(str(FONT/'times.ttf'),18*S)
BODYB=ImageFont.truetype(str(FONT/'timesbd.ttf'),18*S)
HEAD=ImageFont.truetype(str(FONT/'timesbd.ttf'),31*S)
TITLE=ImageFont.truetype(str(FONT/'timesbd.ttf'),38*S)
REL=ImageFont.truetype(str(FONT/'times.ttf'),14*S)

def P(x,y): return (int(x*S),int(y*S))
def center(draw,txt,x,y,font,fill='black'):
    bb=draw.textbbox((0,0),txt,font=font)
    draw.text((int(x*S-(bb[2]-bb[0])/2),int(y*S-(bb[3]-bb[1])/2)),txt,font=font,fill=fill)
def text(draw,txt,x,y,font,fill='black'):
    draw.text(P(x,y),txt,font=font,fill=fill)
def draw_diamond(draw,name,cx,cy,w=132,h=64):
    points=[P(cx,cy-h/2),P(cx+w/2,cy),P(cx,cy+h/2),P(cx-w/2,cy)]
    draw.polygon(points,fill='white',outline='black',width=2*S)
    center(draw,name,cx,cy,REL)
def draw_cardinal(draw,val,x,y):
    bb=draw.textbbox(P(x,y),val,font=BODYB)
    draw.rectangle((bb[0]-3*S,bb[1]-1*S,bb[2]+3*S,bb[3]+1*S),fill='white')
    text(draw,val,x,y,BODYB)
def draw_entity(draw,name,fields,x,y,w=720,h=300):
    header=48
    draw.rectangle((P(x,y),P(x+w,y+h)),fill='white',outline='black',width=2*S)
    draw.rectangle((P(x,y),P(x+w,y+header)),fill='#e5e5e5',outline='black',width=2*S)
    center(draw,name.upper(),x+w/2,y+header/2,BOLD)
    rowh=35
    start=y+header+6
    for i,(field,kind) in enumerate(fields):
        yy=start+i*rowh
        font=ITAL if kind=='FK' else REG
        text(draw,field,x+18,yy,font)
        bb=draw.textbbox(P(x+18,yy),field,font=font)
        # underline primary key attribute names, like the supplied example
        if kind=='PK':
            draw.line((bb[0],bb[3]+1*S,bb[2],bb[3]+1*S),fill='black',width=1*S)
        if kind in ('PK','FK'):
            suffix=f' ({kind})'
            text(draw,suffix,x+18+(bb[2]-bb[0])+8,yy,REG)

def section(draw,title,y):
    x=140
    text(draw,title,x,y,HEAD)
    bb=draw.textbbox(P(x,y),title,font=HEAD)
    draw.line((x*S,bb[3]+6*S,bb[2],bb[3]+6*S),fill='black',width=2*S)

def make_er():
    W,H=2700,2220
    im=Image.new('RGB',(W*S,H*S),'white'); d=ImageDraw.Draw(im)
    center(d,'CHAPTER 5',W/2,62,TITLE); center(d,'DIAGRAMS',W/2,112,TITLE)
    section(d,'5.1 ER Diagram',155)
    text(d,'Each entity is shown as a rectangle containing its attributes. Diamonds show relationships; 1 and N show cardinality.',140,220,BODY)
    text(d,'PK = primary key (underlined); FK = foreign key (italic). Student-Course is many-to-many through Enrollment.',140,252,BODY)
    # Entity positions and all attributes from the LearnHub Chapter 3 model.
    boxes={
      'Instructor':(70,300,[('instructor_id','PK'),('name',''),('email',''),('expertise','')]),
      'Course':(990,300,[('course_id','PK'),('instructor_id','FK'),('title',''),('description',''),('duration_weeks',''),('capacity','')]),
      'Lesson':(1910,300,[('lesson_id','PK'),('course_id','FK'),('lesson_title',''),('lesson_order',''),('duration_minutes','')]),
      'Student':(70,930,[('student_id','PK'),('name',''),('email',''),('phone_no',''),('join_date','')]),
      'Enrollment':(990,930,[('enrollment_id','PK'),('student_id','FK'),('course_id','FK'),('enrollment_date',''),('progress_status','')]),
      'Assignment':(1910,930,[('assignment_id','PK'),('course_id','FK'),('title',''),('due_date',''),('max_marks','')]),
      'Certificate':(70,1560,[('certificate_id','PK'),('enrollment_id','FK'),('certificate_code (UNIQUE)',''),('issue_date','')]),
      'Submission':(990,1560,[('submission_id','PK'),('student_id','FK'),('assignment_id (optional)','FK'),('quiz_id (optional)','FK'),('submission_date',''),('score (may be empty)','')]),
      'Quiz':(1910,1560,[('quiz_id','PK'),('course_id','FK'),('title',''),('total_marks','')]),
    }
    # Connectors and diamonds are drawn before entity boxes.
    # Instructor 1:N Course
    d.line([P(790,450),P(824,450)],fill='black',width=2*S); d.line([P(956,450),P(990,450)],fill='black',width=2*S)
    draw_cardinal(d,'1',798,415); draw_cardinal(d,'N',958,415)
    # Course 1:N Lesson
    d.line([P(1710,450),P(1744,450)],fill='black',width=2*S); d.line([P(1876,450),P(1910,450)],fill='black',width=2*S)
    draw_cardinal(d,'1',1715,415); draw_cardinal(d,'N',1877,415)
    # Student 1:N Enrollment
    d.line([P(790,1080),P(824,1080)],fill='black',width=2*S); d.line([P(956,1080),P(990,1080)],fill='black',width=2*S)
    draw_cardinal(d,'1',798,1045); draw_cardinal(d,'N',958,1045)
    # Course 1:N Enrollment
    d.line([P(1350,600),P(1350,732)],fill='black',width=2*S); d.line([P(1350,796),P(1350,930)],fill='black',width=2*S)
    draw_cardinal(d,'1',1370,635); draw_cardinal(d,'N',1370,850)
    # Course 1:N Assignment via a neat outer branch.
    d.line([P(1710,520),P(1800,520),P(1800,820)],fill='black',width=2*S); d.line([P(1866,820),P(2270,930)],fill='black',width=2*S)
    draw_cardinal(d,'1',1725,485); draw_cardinal(d,'N',2188,905)
    # Course 1:N Quiz, routed around the right side of the other Course relationships.
    d.line([P(1710,600),P(1800,700),P(2680,700),P(2680,1400)],fill='black',width=2*S)
    d.line([P(2548,1400),P(2500,1560)],fill='black',width=2*S)
    draw_cardinal(d,'1',1730,650); draw_cardinal(d,'N',2508,1512)
    # Student 1:N Submission, routed around the bottom margin to keep it separate from Certificate.
    d.line([P(150,1230),P(20,1230),P(20,2040),P(1184,2040)],fill='black',width=2*S)
    d.line([P(1250,2008),P(1250,1860)],fill='black',width=2*S)
    draw_cardinal(d,'1',28,1190); draw_cardinal(d,'N',1270,1867)
    # Assignment 1:N Submission.
    d.line([P(1910,1230),P(1916,1448)],fill='black',width=2*S); d.line([P(1850,1512),P(1710,1590)],fill='black',width=2*S)
    draw_cardinal(d,'1',1885,1205); draw_cardinal(d,'N',1718,1540)
    # Quiz 1:N Submission, along the bottom row.
    d.line([P(1910,1710),P(1876,1710)],fill='black',width=2*S); d.line([P(1744,1710),P(1710,1710)],fill='black',width=2*S)
    draw_cardinal(d,'1',1880,1673); draw_cardinal(d,'N',1714,1673)
    # Enrollment 1:0..1 Certificate.
    d.line([P(1030,1230),P(586,1450)],fill='black',width=2*S); d.line([P(520,1482),P(700,1560)],fill='black',width=2*S)
    draw_cardinal(d,'1',1000,1240); draw_cardinal(d,'0..1',700,1510)
    # Relationship diamonds on top of connectors.
    for name,cx,cy,w,h in [
      ('Teaches',890,450,132,64),('Contains',1810,450,132,64),('Enrolls',890,1080,132,64),
      ('Has',1350,764,132,64),('Sets',1800,820,132,64),('Includes',2614,1400,132,64),
      ('Submits',1250,2040,132,64),('For',1850,1480,132,64),('For',1810,1710,132,64),('Issues',520,1450,132,64)]:
        draw_diamond(d,name,cx,cy,w,h)
    # Entity cards over the connectors.
    for name,(x,y,fields) in boxes.items(): draw_entity(d,name,fields,x,y)
    text(d,'A submission is for either an Assignment or a Quiz. A completed Enrollment may have at most one Certificate.',140,2110,BODY)
    center(d,'Figure 5.1: ER diagram of the LearnHub database',W/2,2165,REG)
    im.resize((W*S,H*S),Image.Resampling.LANCZOS).save(ROOT/'LearnHub_ER_Diagram.png',dpi=(220,220),optimize=True)

def make_schema():
    # A report-style page: textual relational schema followed by the linked relation boxes.
    W,H,S2=3000,3000,2
    im=Image.new('RGB',(W*S2,H*S2),'white'); d=ImageDraw.Draw(im)
    def p(x,y): return (int(x*S2),int(y*S2))
    def t(txt,x,y,font=BODY,fill='black'): d.text(p(x,y),txt,font=font,fill=fill)
    def c(txt,x,y,font=BODY):
        bb=d.textbbox((0,0),txt,font=font); d.text((int(x*S2-(bb[2]-bb[0])/2),int(y*S2-(bb[3]-bb[1])/2)),txt,font=font,fill='black')
    c('CHAPTER 5',W/2,58,TITLE); c('DIAGRAMS',W/2,108,TITLE)
    t('5.2 Relational Schema',140,160,HEAD)
    bb=d.textbbox(p(140,160),'5.2 Relational Schema',font=HEAD); d.line((140*S2,bb[3]+6*S2,bb[2],bb[3]+6*S2),fill='black',width=2*S2)
    t('Primary keys are underlined and foreign keys are shown in italics.',140,220,BODY)
    # Clean, readable relation notation, arranged as two columns.
    relations=[
      ('Student','student_id, name, email, phone_no, join_date',['student_id'],[]),
      ('Instructor','instructor_id, name, email, expertise',['instructor_id'],[]),
      ('Course','course_id, instructor_id, title, description, duration_weeks, capacity',['course_id'],['instructor_id']),
      ('Enrollment','enrollment_id, student_id, course_id, enrollment_date, progress_status',['enrollment_id'],['student_id','course_id']),
      ('Lesson','lesson_id, course_id, lesson_title, lesson_order, duration_minutes',['lesson_id'],['course_id']),
      ('Assignment','assignment_id, course_id, title, due_date, max_marks',['assignment_id'],['course_id']),
      ('Quiz','quiz_id, course_id, title, total_marks',['quiz_id'],['course_id']),
      ('Submission','submission_id, student_id, assignment_id?, quiz_id?, submission_date, score',['submission_id'],['student_id','assignment_id?','quiz_id?']),
      ('Certificate','certificate_id, enrollment_id, certificate_code (UNIQUE), issue_date',['certificate_id'],['enrollment_id']),
    ]
    # Relation definitions with conventional notation and readable key styling.
    cols=[140,1560]; ys=[300,410,520,630,740]
    for idx,(name,fields,pks,fks) in enumerate(relations):
        col=idx//5; row=idx%5; x=cols[col]; y=ys[row]
        t(name+' (',x,y,BODYB)
        cur=x+d.textbbox((0,0),name+' (',font=BODYB)[2]/S2
        for j,f in enumerate(fields.split(', ')):
            if j: t(', ',cur,y,BODY); cur+=d.textbbox((0,0),', ',font=BODY)[2]/S2
            font=ITAL if f in fks else REG
            t(f,cur,y,font)
            bb2=d.textbbox(p(cur,y),f,font=font)
            if f in pks: d.line((bb2[0],bb2[3]+1*S2,bb2[2],bb2[3]+1*S2),fill='black',width=S2)
            cur+=(bb2[2]-bb2[0])/S2
            if cur>x+1250 and j<len(fields.split(', '))-1:
                t(',',cur,y,BODY); y+=30; cur=x+45
        t(' )',cur,y,BODY)
    t('Linked relation boxes (foreign-key references)',140,900,HEAD)
    # Compact relation boxes arranged to group parent and child tables.
    boxes={
      'Instructor':(100,1100,[('instructor_id','PK'),('name',''),('email',''),('expertise','')]),
      'Course':(1150,1100,[('course_id','PK'),('instructor_id','FK'),('title',''),('description',''),('duration_weeks',''),('capacity','')]),
      'Lesson':(2200,1100,[('lesson_id','PK'),('course_id','FK'),('lesson_title',''),('lesson_order',''),('duration_minutes','')]),
      'Student':(100,1680,[('student_id','PK'),('name',''),('email',''),('phone_no',''),('join_date','')]),
      'Enrollment':(1150,1680,[('enrollment_id','PK'),('student_id','FK'),('course_id','FK'),('enrollment_date',''),('progress_status','')]),
      'Assignment':(2200,1680,[('assignment_id','PK'),('course_id','FK'),('title',''),('due_date',''),('max_marks','')]),
      'Certificate':(100,2260,[('certificate_id','PK'),('enrollment_id','FK'),('certificate_code',''),('issue_date','')]),
      'Submission':(1150,2260,[('submission_id','PK'),('student_id','FK'),('assignment_id?','FK'),('quiz_id?','FK'),('submission_date',''),('score','')]),
      'Quiz':(2200,2260,[('quiz_id','PK'),('course_id','FK'),('title',''),('total_marks','')]),
    }
    # FK arrows, routed through open gutters so the table boxes remain legible.
    pending_arrows=[]
    def arrow(points): pending_arrows.append(points)
    def draw_arrow(points):
        coords=[p(*xy) for xy in points]; d.line(coords,fill='#333333',width=2*S2,joint='curve')
        x1,y1=coords[-2]; x2,y2=coords[-1]; import math
        ang=math.atan2(y2-y1,x2-x1); L=10*S2
        a=(int(x2-L*math.cos(ang-.45)),int(y2-L*math.sin(ang-.45))); b=(int(x2-L*math.cos(ang+.45)),int(y2-L*math.sin(ang+.45)))
        d.polygon([(x2,y2),a,b],fill='#333333')
    # Connections terminate at the parent entity border and avoid text areas.
    arrow([(1150,1240),(820,1240),(820,1150),(800,1150)]) # Course -> Instructor
    arrow([(2200,1240),(1940,1240),(1940,1150),(1850,1150)]) # Lesson -> Course
    arrow([(1150,1810),(800,1810)]) # Enrollment -> Student
    arrow([(1450,1680),(1450,1400)]) # Enrollment -> Course
    arrow([(2200,1740),(2070,1600),(1970,1500),(1850,1390)]) # Assignment -> Course
    arrow([(2200,2320),(1960,2320),(1960,1450),(1850,1370)]) # Quiz -> Course
    arrow([(1150,2260),(850,2260),(850,2200),(60,2200),(60,1810),(100,1810)]) # Submission -> Student
    arrow([(2550,1980),(2320,2110),(1800,2260)]) # Assignment -> Submission
    arrow([(2200,2420),(1850,2420)]) # Submission -> Quiz
    arrow([(450,2260),(450,2100),(1150,1900)]) # Certificate -> Enrollment
    for name,(x,y,fields) in boxes.items(): draw_entity(d,name,fields,x,y,w=700,h=300)
    for points in pending_arrows: draw_arrow(points)
    t('Arrows point from each foreign key to its referenced primary key. ? marks an optional foreign key; each submission is for an assignment or a quiz.',140,2680,BODY)
    c('Figure 5.2: Relational schema diagram of the LearnHub database',W/2,2870,REG)
    im.save(ROOT/'LearnHub_Relational_Schema.png',dpi=(220,220),optimize=True)

if __name__=='__main__':
    make_er()
    make_schema()
    print(ROOT/'LearnHub_ER_Diagram.png')
    print(ROOT/'LearnHub_Relational_Schema.png')

