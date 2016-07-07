import Tkinter as tk
import ttk

import cv2
from PIL import Image, ImageTk
import numpy as np
import time
import math

import tkMessageBox

from mpl_toolkits.mplot3d import Axes3D
from scipy.ndimage.interpolation import zoom

import matplotlib
matplotlib.use('TkAgg')

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from lib import analysis
from lib import output

root = tk.Tk()
lmain = tk.Label(root)
lmain.pack()

class InfoFrame(tk.Frame):
    def __init__(self, parent):

	self.window = tk.Toplevel(parent)

        self.window.minsize(200,300)
        self.tree = ttk.Treeview(self.window,columns=("Unit","Value"))
        self.tree.heading("#0", text='Parameter', anchor=tk.W)
        self.tree.column("#0", stretch=0)
        self.tree.heading("#1", text='Unit', anchor=tk.W)
        self.tree.column("#1", stretch=0)
        self.tree.heading("#2", text='Value', anchor=tk.W)
        self.tree.column("#2", stretch=0)

        self.raw_rows = ["Beam Width (4 sigma)", "Beam Diameter (4 sigma)", "Effective Beam Diameter", "Peak Position", "Centroid Position", "Total Power"]
        self.raw_units = ["um"]*len(self.raw_rows)
        self.ellipse_rows = ["Ellipse axes", "Ellipticity", "Eccentricity", "Orientation"]
        self.ellipse_units = ["um", "%", "%", "deg"]
        
        self.tree.insert("",iid="1", index="end",text="Raw Data Measurement")
        for i in range(len(self.raw_rows)):
            self.tree.insert("1",iid="1"+str(i), index="end", text=self.raw_rows[i], value=(self.raw_units[i],np.random.random()))
        self.tree.see("14")
        self.tree.insert("",iid="2", index="end",text="Ellipse (fitted)")
        for i in range(len(self.ellipse_rows)):
            self.tree.insert("2",iid="2"+str(i), index="end", text=self.ellipse_rows[i], value=(self.ellipse_units[i],np.random.random()))
        self.tree.see("23")
        
        self.tree.pack(expand=True,fill=tk.BOTH)
        
        button_refresh = tk.Button(self.window, text="refresh", command=self.refresh_frame)
        button_refresh.pack()
        
        self.refresh_frame()
    
    def refresh_frame(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("",iid="1", index="end",text="Raw Data Measurement")
        for i in range(len(self.raw_rows)):
            self.tree.insert("1",iid="1"+str(i), index="end", text=self.raw_rows[i], value=(self.raw_units[i],np.random.random()))
        self.tree.see("14")
        self.tree.insert("",iid="2", index="end",text="Ellipse (fitted)")
        for i in range(len(self.ellipse_rows)):
            self.tree.insert("2",iid="2"+str(i), index="end", text=self.ellipse_rows[i], value=(self.ellipse_units[i],np.random.random()))
        self.tree.see("23")

    def close(self):
        self.window.destroy()
        
class Controller(tk.Frame):
    def __init__(self, parent=root):
        '''Initialises basic variables and GUI elements.'''
        self.active = False
        self.pause_delay = 0 #time delay for when profiler is inactive. cumulatively adds.
        self.last_pause = time.time() #last time profiler was inactive
        self.plot_time = self.last_pause  #various parameters ters used throughout the profiler are initialised here
        self.angle = 0
        self.roi = 1
        self.camera_index = 0
        self.centroid = None
        self.peak_cross = None
        self.colourmap = None
        self.fig_type = 'cross profile'
        self.counter = 0
        self.top2 = None
        self.running_time = np.array([]) #arrays for information logged throughout the running period
        self.centroid_hist_x, self.centroid_hist_y = np.array([]), np.array([])
        self.peak_hist_x, self.peak_hist_y = np.array([]), np.array([])
        self.MA, self.ma, self.ellipse_x, self.ellipse_y, self.ellipse_angle = 0, 0, 0, 0, 0

	self.info_frame = None

        frame = tk.Frame.__init__(self, parent,relief=tk.GROOVE,width=100,height=100,bd=1)
        self.parent = parent
        self.var = tk.IntVar()

        self.parent.title('Laser Beam Profiler')
        
        ###################################################################NAVBAR
        menubar = tk.Menu(self.parent)
        fileMenu = tk.Menu(menubar, tearoff=0)
        fileMenu.add_command(label="Calculation Results", command=self.calc_results)
        fileMenu.add_command(label="Export Data", command=self.save_csv)
        fileMenu.add_separator()
        fileMenu.add_command(label="Quit", command=self.close_window)
        menubar.add_cascade(label="File", menu=fileMenu)
        
        controlMenu = tk.Menu(menubar, tearoff=0)
        submenu = tk.Menu(controlMenu, tearoff=0)
        submenu.add_command(label="0", command= lambda: self.change_cam(0))
        submenu.add_command(label="1", command= lambda: self.change_cam(1))
        submenu.add_command(label="2", command= lambda: self.change_cam(2))
        controlMenu.add_cascade(label='Change Camera', menu=submenu, underline=0)
        controlMenu.add_separator()
        controlMenu.add_command(label="Clear Windows", command= lambda: tkMessageBox.showerror("Not done", "This is a temporary message"))
        menubar.add_cascade(label="Control", menu=controlMenu)

        imageMenu = tk.Menu(menubar, tearoff=0)       
        imageMenu.add_command(label="Take Screenshot", command=self.save_screenshot)
        imageMenu.add_command(label="Take Video /10 s", command=lambda: self.save_video(10))
        imageMenu.add_separator()
        submenu = tk.Menu(imageMenu, tearoff=0)
        submenu.add_command(label="Normal", command= lambda: self.change_colourmap('normal'))
        submenu.add_command(label="Jet", command= lambda: self.change_colourmap('jet'))
        submenu.add_command(label="Autumn", command=lambda: self.change_colourmap('autumn'))
        submenu.add_command(label="Bone", command=lambda: self.change_colourmap('bone'))
        imageMenu.add_cascade(label='Change Colourmap', menu=submenu, underline=0)
        
        menubar.add_cascade(label="Image", underline=0, menu=imageMenu)        
        
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=lambda: self.info_window("Laser Beam Profiler created by Samuel Bancroft \n Summer 2016 Internship Project \n Supervisor: Dr Jon Goldwin, Birmingham University", modal=True))
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.parent.config(menu=menubar)
        ###################################################################NAVBAR
       
        labelframe = tk.Frame(self) #left hand frame for various sliders and tweakables for direct control
        labelframe.pack(side=tk.LEFT) #.grid(row=0, column=0) 
        
        self.scale1 = tk.Scale(labelframe, label='exposure',
            from_=-100000, to=-100,
            length=300, tickinterval=10000,
            showvalue='yes', 
            orient='horizontal',
            command = self.change_exp)
        self.scale1.pack()
        
        self.scale2 = tk.Scale(labelframe, label='ROI',
            from_=1, to=50,
            length=300, tickinterval=1,
            showvalue='yes', 
            orient='horizontal',
            command = self.set_roi)
        self.scale2.pack()
        
        # self.scale2 = tk.Scale(labelframe, label='gain',
            # from_=-10000, to=10000,
            # length=300, tickinterval=1,
            # showvalue='yes', 
            # orient='horizontal',
            # command = self.change_gain)
        # self.scale2.pack()
        
        self.scale3 = tk.Scale(labelframe, label='rotate',
            from_=0, to=360,
            length=300, tickinterval=30,
            showvalue='yes', 
            orient='horizontal',
            command = self.set_angle)
        self.scale3.pack()
        
        self.variable3 = tk.StringVar(labelframe)
        self.variable3.set("cross profile")
        self.dropdown3 = tk.OptionMenu(labelframe, self.variable3, "cross profile", "2d gaussian fit","2d surface", "beam stability", "centroid/peak cross history", "ellipse fit", command = self.change_fig)
        self.dropdown3.pack()
        
        self.variable4 = tk.IntVar()
        rb = tk.Checkbutton(labelframe, text="Profiler Active", variable=self.variable4, command=self.profiler_active)
        rb.pack(fill=tk.BOTH)
        
        b = tk.Button(labelframe, text="Sound", command=lambda: output.main())
        b.pack(fill=tk.BOTH)

        self.make_fig() #make figure environment
        self.init_camera() #initialise camera
        self.show_frame() #show video feed and update view with new information and refreshed plot etc

    def make_fig(self):
        '''Creates a matplotlib figure to be placed in the GUI.'''
        plt.clf()
        plt.cla()
        
        if self.fig_type == 'cross profile':
            self.fig, self.ax = plt.subplots(1,2, gridspec_kw = {'width_ratios':[16, 9]})
        elif self.fig_type == '2d gaussian fit':
            self.fig = Figure(figsize=(4,4), dpi=100)
        elif self.fig_type == '2d surface':
            self.fig = Figure(figsize=(4,4), projection='3d', dpi=100)
        elif self.fig_type == 'beam stability':
            self.fig = Figure(figsize=(4,4), dpi=100)
        elif self.fig_type == 'centroid/peak cross history':
            self.fig = Figure(figsize=(4,4), dpi=100)
        elif self.fig_type == 'ellipse fit':
            self.fig = Figure(figsize=(4,4), dpi=100)

        # self.ax.set_ylim(0,255)
        canvas = FigureCanvasTkAgg(self.fig, self) 
        canvas.show() 
        canvas.get_tk_widget().pack() 

        toolbar = NavigationToolbar2TkAgg(canvas, self) 
        toolbar.update() 
        canvas._tkcanvas.pack()
        
    def refresh_plot(self):
        '''Updates the matplotlib figure with new data.'''
        
        grayscale = np.array(Image.fromarray(self.img).convert('L'))
        
        if self.fig_type == 'cross profile':
            if self.peak_cross != None:
                # print 'beam width:', 4*np.std(grayscale[self.centroid[1],:]),4*np.std(grayscale[:,self.centroid[0]])
                self.ax[0].plot(range(self.height), grayscale[self.peak_cross[1],:],'k-')
                self.ax[1].plot(grayscale[:,self.peak_cross[0]], range(self.width),'k-')
                
                self.ax[0].set_xlim(0,self.height)
                self.ax[0].set_ylim(0,255)
                
                self.ax[1].set_xlim(0,255)
                self.ax[1].set_ylim(self.width,0)              
        elif self.fig_type == '2d gaussian fit':
            if self.peak_cross != None:
                size = 50
                x, y = self.peak_cross
                img = grayscale[y-size/2:y+size/2, x-size/2:x+size/2]
                params = analysis.fit_gaussian(img, with_bounds=False)
                # plt.imshow(self.img[y-size/2:y+size/2, x-size/2:x+size/2]) #show image for debug purposes.
                analysis.plot_gaussian(plt.gca(), img, params)
        elif self.fig_type == '2d surface':
            ax = self.fig.add_subplot(1,1,1,projection='3d')
            z = np.asarray(grayscale)[100:250,250:400]
            z = zoom(z, 0.25)
            mydata = z[::1,::1]
            x,y = np.mgrid[:mydata.shape[0],:mydata.shape[1]]
            ax.plot_surface(x,y,mydata,cmap=plt.cm.jet,rstride=1,cstride=1,linewidth=0.,antialiased=False)
            ax.set_zlim3d(0,255)
        elif self.fig_type == 'beam stability':
            plt.plot(self.centroid_hist_x, self.centroid_hist_y)
            plt.xlim(0, self.height)
            plt.ylim(self.width, 0)
        elif self.fig_type == 'centroid/peak cross history':
            plt.plot(self.running_time-self.running_time[0], self.centroid_hist_x, 'b-', label='centroid x coordinate')
            plt.plot(self.running_time-self.running_time[0], self.centroid_hist_y, 'r-', label='centroid y coordinate')
            plt.plot(self.running_time-self.running_time[0], self.peak_hist_x, 'y-', label='peak x coordinate')
            plt.plot(self.running_time-self.running_time[0], self.peak_hist_y, 'g-', label='peak y coordinate')
            if self.running_time[-1] - self.running_time[0] <= 60:
                plt.xlim(0, 60)
            else:
                index = np.searchsorted(self.running_time,[self.running_time[-1]-60,],side='right')[0]
                plt.xlim(self.running_time[index]-self.running_time[0], self.running_time[-1]-self.running_time[0])
            plt.ylim(0,self.height)
            plt.legend(frameon=False)
        elif self.fig_type == 'ellipse fit':
            pts = analysis.get_ellipse_coords(a=self.ma, b=self.MA, x=self.ellipse_x, y=self.ellipse_y, angle=-self.ellipse_angle)
            plt.plot(pts[:,0], pts[:,1])
            
            MA_x, MA_y = self.ma*math.cos(self.ellipse_angle*(np.pi/180)), self.ma*math.sin(self.ellipse_angle*(np.pi/180))
            ma_x, ma_y = self.MA*math.sin(self.ellipse_angle*(np.pi/180)), self.MA*math.cos(self.ellipse_angle*(np.pi/180))
            MA_xtop, MA_ytop = int(self.ellipse_x + MA_x), int(self.ellipse_y + MA_y)
            MA_xbot, MA_ybot = int(self.ellipse_x - MA_x), int(self.ellipse_y - MA_y)
            ma_xtop, ma_ytop = int(self.ellipse_x + ma_x), int(self.ellipse_y + ma_y) #find corners of ellipse
            ma_xbot, ma_ybot = int(self.ellipse_x - ma_x), int(self.ellipse_y - ma_y)
            
            plt.plot(MA_xtop, MA_ytop, 'ro')
            plt.plot(MA_xbot, MA_ybot, 'bo')
            plt.plot(ma_xtop, ma_ybot, 'rx')
            plt.plot(ma_xbot, ma_ytop, 'bx')

            # print np.dot([ma_xtop-ma_xbot, ma_ytop-ma_ybot], [MA_xtop-MA_xbot, MA_ytop-MA_ybot]) #axes not always perfectly perpendicular
            
            plt.xlim(0, self.height)
            plt.ylim(self.width, 0)
            
        # self.ax[0].hold(True)
        # self.ax[1].hold(True)
        self.fig.canvas.draw() 
        
        for axis in self.fig.get_axes():
            axis.clear()
    
    def change_fig(self, option):
        '''Changes the fig used.'''
        if self.fig_type != option:
            print 'changed fig', option
            self.fig_type = option
            plt.cla()
            plt.clf()
            
    def change_exp(self, option):
        '''Changes the exposure time of the camera.'''
        exp = float(option)
        print 'changing exp to', exp
        self.cap.set(15, exp)
        
    def change_gain(self, option):
        '''Changes the gain of the camera.'''
        gain = float(option)
        print 'changing gain to', gain
        self.cap.set(14, gain)

    def init_camera(self):
        '''Initialises the camera with a set resolution.'''
        self.height, self.width = 640, 360
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap:
            raise Exception("Camera not accessible")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.height)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.width)
                  
    def change_cam(self, option):
        '''Switches between camera_indexes and therefore different connected cameras.'''
        if self.camera_index != option and type(option) == int:
            self.camera_index = int(option)
            print 'camera index change, now updating view...', self.camera_index
            self.cap.release()
            self.init_camera()
            self.show_frame()
    
    def change_colourmap(self, option):
        '''Changes the colourmap used in the camera feed.'''
        if self.colourmap != option:
            print 'changed colourmap to ', option
            if option.lower() == 'jet':
                self.colourmap = cv2.COLORMAP_JET
            elif option.lower() == 'autumn':
                self.colourmap = cv2.COLORMAP_AUTUMN
            elif option.lower() == 'bone':
                self.colourmap = cv2.COLORMAP_BONE
            else:
                self.colourmap = None
            
    def show_frame(self):
        '''Shows camera view with relevant labels and annotations included.'''
        _, frame = self.cap.read() #read camera input
        # frame = cv2.flip(frame, 1)
        
        if self.roi != 1: #apply region of interest scaling
            size = int(round(self.height/self.roi)), int(round(self.width/self.roi))
            frame = frame[self.width/2-size[1]:self.width/2+size[1], self.height/2-size[0]:self.height/2+size[0]]
            dim1 = frame.shape
            frame = cv2.resize(frame,None,fx=self.roi/2, fy=self.roi/2, interpolation = cv2.INTER_CUBIC)
            
        if self.colourmap is None: #apply colourmap change
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        else:
            cv2image = cv2.applyColorMap(frame, self.colourmap)
            
        if self.angle != 0: #apply rotation
            cv2image = self.rotate_image(cv2image)
        
        dim = np.shape(cv2image)
        
        if self.active:
            cv2.putText(cv2image,"Laser Beam profiler: ACTIVE", (10,40), cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
            # convert to greyscale
            tracking = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                 
            centroid = analysis.find_centroid(tracking)
            if centroid != (np.nan, np.nan):
            
                #if centroid then peak cross can be calculated quickly
                i,j = analysis.get_max(tracking, np.std(tracking), alpha=10, size=10) #make sure not too intensive
                if len(i) != 0 and len(j) != 0:
                    peak_cross = (sum(i) / len(i), sum(j) / len(j)) #chooses the average point for the time being!!
                    self.peak_cross = peak_cross
                else:
                    peak_cross = (np.nan, np.nan)
                    self.peak_cross = None
                    
                size = 50
                if self.peak_cross is not None: #temp until ROI is implemented
                    x, y = self.peak_cross
                else:
                    x, y = 0,0
                cropped = tracking[y-size/2:y+size/2, x-size/2:x+size/2]
                cv2.putText(cv2image,'Average Power: ' + str(round(np.mean(cropped),2)), (10,255), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0)) #NEEDS WAY MORE WORK
                cv2.putText(cv2image,'Total Power: ' + str(round(np.sum(cropped),2)), (10,270), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0)) #masking, thresholding, correct units required
                
                cv2.putText(cv2image,'Min Value: ' + str(np.min(tracking)), (10,340), cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
                
                if peak_cross != (np.nan, np.nan):
                    cv2.putText(cv2image,'Max Value: ' + str(np.max(tracking)) + ' at (' + str(int(peak_cross[0]))+ ', ' + str(int(peak_cross[1])) + ')', (10,325), cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
                    # cv2.circle(cv2image,(int(peak_cross[0]), int(peak_cross[1])),10,255,thickness=3)
                
                if centroid[0] < self.height or centroid[1] < self.width: #ensure centroid lies within correct regions
                    # cv2.circle(cv2image,centroid,10,255,thickness=10)
                    cv2.putText(cv2image,'Centroid position: ' + str(centroid), (10,310), cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
                    self.centroid = centroid
                    
                    cv2.line(cv2image, (0, centroid[1]), (self.height, centroid[1]), 255, thickness=1)
                    cv2.line(cv2image, (centroid[0], 0), (centroid[0], self.width), 255, thickness=1)
                    
                else:
                    print 'Problem! Centroid out of image region.', centroid[0], centroid[1]
                    self.centroid = None
            else:
                self.centroid = None
                peak_cross = (np.nan, np.nan)
                self.peak_cross = None

            #record data that should be logged throughout time
            self.centroid_hist_x, self.centroid_hist_y = np.append(self.centroid_hist_x, centroid[0]), np.append(self.centroid_hist_y, centroid[1])
            self.peak_hist_x, self.peak_hist_y = np.append(self.peak_hist_x, peak_cross[0]), np.append(self.peak_hist_y, peak_cross[1])
            self.running_time = np.append(self.running_time, time.time()-self.pause_delay) #making sure to account for time that pause has been active
        
            ellipses = analysis.find_ellipses(tracking) #fit ellipse and print data to screen
            if ellipses != None:
                (x,y),(ma,MA),angle = ellipses
                self.MA, self.ma, self.ellipse_x, self.ellipse_y, self.ellipse_angle = MA, ma, x, y, angle
                cv2.putText(cv2image,'Ellipse fit active', (420,295), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0))
                cv2.putText(cv2image,'Ellipticity: ' + str(round(1-(self.ma/self.MA),2)), (420,310), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0))
                cv2.putText(cv2image,'Eccentricity: ' + str(round(np.sqrt(1-(self.ma/self.MA)**2),2)), (420,325), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0))
                cv2.putText(cv2image,'Orientation (deg): ' + str(round(self.ellipse_angle,2)), (420,340), cv2.FONT_HERSHEY_PLAIN, 1, (255,0,0))
                cv2.ellipse(cv2image,ellipses,(0,255,0),1)

        imgtk = ImageTk.PhotoImage(image=Image.fromarray(cv2image))
            
        lmain.imgtk = imgtk
        lmain.configure(image=imgtk)
        lmain.after(10, self.show_frame)
        
        self.img = frame
        if time.time() - self.plot_time > 0.1 and self.active: #if tickrate period elapsed, update the plot with new data
            self.refresh_plot()
            self.plot_time = time.time()
        
    def set_angle(self, option):
        '''Sets the rotation angle.'''
        self.angle = float(option)
        
    def set_roi(self, option):
        '''Sets the region of interest size'''
        print 'changed roi to', option
        self.roi = float(option)
        
    def profiler_active(self):
        '''Turns profiling mode on or off'''
        if self.variable4.get() == 1 and not self.active:
            print 'Profiler ACTIVE'
            self.pause_delay += time.time()-self.last_pause
            self.active = True
        elif self.variable4.get() == 0 and self.active:
            print 'Profiler INACTIVE'
            self.last_pause = time.time()
            self.active = False
        
    def rotate_image(self, image):
        '''Rotates the given array by the rotation angle, returning as an array.'''
        image_height, image_width = image.shape[0:2]
        
        image_rotated = output.rotate_image(image, self.angle)
        image_rotated_cropped = output.crop_around_centre(
            image_rotated,
            *output.largest_rotated_rect(
                image_width,
                image_height,
                math.radians(self.angle)
            )
        )
        return image_rotated_cropped
  
    def close_window(self):
        on_closing()
        
    def info_window(self, info, modal=False):
        self.counter += 1
        t = tk.Toplevel(self)
        t.wm_title("Window #%s" % self.counter)
        l = tk.Label(t, text=info)
        # l = tk.Label(t, text="This is window #%s" % self.counter)
        l.pack(side="top", fill="both", expand=True, padx=100, pady=100)
        if modal:
            l.focus_set()                                                        
            l.grab_set()  
       
    def save_screenshot(self):
        cv2.imwrite('output.png', self.img)
        
    def save_video(self, wait):
        start = time.time()
        # zeros array
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = None
        (h, w) = (None, None)
        zeros = None
        # loop over frames from the video stream
        while wait > time.time() - start:
            # grab the frame from the video stream and resize it to have a
            # maximum width of 300 pixels
            _, frame = self.cap.read()
            # check if the writer is None
            if writer is None:
                # store the image dimensions, initialzie the video writer,
                # and construct the zeros array
                (h, w) = (self.width, self.height)
                writer = cv2.VideoWriter("output.avi", fourcc, 30,
                    (w * 2, h * 2), True)
                zeros = np.zeros((h, w), dtype="uint8")
        
                # break the image into its RGB components, then construct the
                # RGB representation of each frame individually
                B, G, R = cv2.split(frame)
                R = cv2.merge([zeros, zeros, R])
                G = cv2.merge([zeros, G, zeros])
                B = cv2.merge([B, zeros, zeros])
             
                # construct the final output frame, storing the original frame
                # at the top-left, the red channel in the top-right, the green
                # channel in the bottom-right, and the blue channel in the
                # bottom-left
                output = np.zeros((h * 2, w * 2, 3), dtype="uint8")
                output[0:h, 0:w] = frame
                output[0:h, w:w * 2] = R
                output[h:h * 2, w:w * 2] = G
                output[h:h * 2, 0:w] = B
             
                # write the output frame to file
                writer.write(output)
            
    def save_csv(self):
        '''Saves .csv file of recorded data in columns.'''
        output = np.column_stack((self.running_time.flatten(),self.centroid_hist_x.flatten(),self.centroid_hist_y.flatten()))
        np.savetxt('output.csv',output,delimiter=',',header='Laser Beam Profiler Data Export. \n running time, centroid_hist_x, centroid_hist_y')
    
    def calc_results(self):
        try:
            self.top2.focus_set()
            return
        except Exception:
            pass
            
	if self.info_frame != None:
		self.info_frame.close()
	self.info_frame = InfoFrame(self)
        
def on_closing():
        '''Closes the GUI.'''
        root.quit()
        root.destroy()
        c.cap.release()
        cv2.destroyAllWindows()
        
c = Controller(root)
c.pack()
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
