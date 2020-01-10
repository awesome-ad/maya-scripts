# coding: UTF-8

# -------------------------
# A proof of concept port of aweControlPicker
# from Maya to Motionbuilder
# -------------------------

from pyfbsdk import *
import pyfbsdk_additions as pyui
from PySide import QtGui

gDeveloperMode = True

def log(*messages):
	'''Wrapper around print statement to control script output'''

	if gDeveloperMode:
		message = ""
		for m in range(len(messages)):
			bit = str(messages[m])
			sep = " " if m else ""
			message += sep + bit
		print message

class Picker(object):
	'''The internal Picker object

	This class stores and manages the state of each Picker.
	There should only be one Picker instance per Picker, and it should be passed
	around to the UI etc.
	'''

	def __init__(self, name="Picker", objectList=[],pickerObject=None, tab="Pickers"):
		self.pickerObject = self.createPickerObject(name, tab, pickerObject, objectList)

	@property
	def name(self):
		if self.pickerObject:
			return self.pickerObject.PropertyList.Find('PickerName').Data
		else:
			return "Unknown"
	@name.setter
	def name(self, value):
		self.pickerObject.PropertyList.Find('PickerName').Data = value
		self.pickerObject.Name = value

	@property
	def tab(self):
	    return self.pickerObject.PropertyList.Find('Tab').Data
	@tab.setter
	def tab(self, value):
	    self.pickerObject.PropertyList.Find('Tab').Data = value
	    self.pickerObject.Tab = value
	
	@property
	def objects(self):
		return [o for o in self.pickerObject.PropertyList.Find('Objects')]
	@objects.setter
	def objects(self, objectList):
		self.pickerObject.PropertyList.Find('Objects').removeAll()
		for o in objectList:
			self.pickerObject.PropertyList.Find('Objects').append(o)
	

	def createPickerObject(self, name, tab, pickerObject, objectList=[]):
		'''Creates the Set object used to store the Picker in the Scene

		When used during initPickers(), it doesn't create a new set and
		returns the existing set instead.
		'''

		po = pickerObject
		if not po:
			po = aweCreateSet(name)
			# search for master set. If none found, create it.
			masterSet = None
			for s in FBSystem().Scene.Sets:
				if s.LongName == "awe:Pickers":
					masterSet = s
			if not masterSet:
				masterSet = aweCreateSet("awe:Pickers")
			# search for the tab set. If none found, create it.
			tabSet = None
			for s in masterSet.Items:
				if s.ClassName() == 'FBSet' and s.LongName == tab:
					tabSet = s
			if not tabSet:
				tabSet = aweCreateSet(tab)
				masterSet.ConnectSrc(tabSet)
			tabSet.ConnectSrc(po)

			po.PropertyCreate('PickerName', FBPropertyType.kFBPT_charptr, 'String', False, False, None)
			po.PropertyCreate('Objects', FBPropertyType.kFBPT_object, 'Object', False, False, None)
			po.PropertyList.Find("PickerName").Data = name
			po.Pickable = po.Transformable = False
			for o in objectList:
				po.PropertyList.Find('Objects').append(o)
			po.picker = self
		po.OnUnbind.Add(_pickerObjectDestroyed)
		return po

	def rename(self, newName):
		self.name = newName
		return self.name

	def select(self):
		'''Selects all objects associated with this Picker
		'''
		if self.pickerObject:
			FBBeginChangeAllModels()
			ml = FBModelList()
			FBGetSelectedModels(ml)
			for m in ml:
				m.Selected = False
			for o in self.objects:
				o.Selected = True
			FBEndChangeAllModels()
			return True
		else:
			return False

	def delete(self):
		'''Deletes this Picker's associated pickerObject'''

		if self.pickerObject:
			self.pickerObject.FBDelete()

	def add(self,objectList):
		'''Adds a list of objects to this Picker'''

		objects = self.objects
		objects.extend(objectList)
		# remove duplicates
		tempSet = set(objects)
		self.objects = [o for o in tempSet]


def aweCreateSet(name):
	Set = FBSet("")
	Set.LongName = name
	disallowedFlags = [FBObjectFlag.kFBFlagBrowsable, FBObjectFlag.kFBFlagRenamable]
	#for flag in disallowedFlags:
		#Set.DisableObjectFlags(flag)
	return Set

def _createPicker(control,event):
	'''Callback:
	Creates Picker and its UI after prompting for a name
	'''

	ml = FBModelList()
	FBGetSelectedModels(ml)
	objSet = []
	for m in ml:
		objSet.append(m)
	if not objSet:
		FBMessageBox("Picker Error", "Error: No Objects selected","OK")
	else:
		userInput = FBMessageBoxGetUserValue("Create New Picker", "Name: ", "Picker", FBPopupInputType.kFBPopupString, "OK", "Cancel",None,1,True)
		if userInput[0] == 1:
			name = userInput[1]
			picker = Picker(name,objSet)
			createPickerButton(name,picker)
			_toolResize()


def createPickerButton(name,picker):
	'''Creates Picker button UI and associates it with given Picker object'''

	box = FBLayout()
	box.picker = picker


	# optionBtn region
	x = FBAddRegionParam(0, FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(0, FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(20, FBAttachType.kFBAttachNone,"")
	h = FBAddRegionParam(25, FBAttachType.kFBAttachNone,"")
	box.AddRegion("optionBtnRegion", "optionBtnRegion", x,y,w,h)

	box.optionBtn = FBButton()
	box.optionBtn.Caption = "»"
	#box.optionBtn.Look = FBButtonLook.kFBLookColorChange
	#box.optionBtn.Style = FBButtonStyle.kFB2States
	box.optionBtn.optionBoxVisible = False
	box.optionBtn.picker = picker
	box.optionBtn.OnClick.Add(_toggleOptionMenu)
	box.SetControl("optionBtnRegion", box.optionBtn)

	# picker / optionBox region
	x = FBAddRegionParam(0, FBAttachType.kFBAttachRight,"optionBtnRegion")
	y = FBAddRegionParam(0, FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(0, FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(25, FBAttachType.kFBAttachNone,"")
	box.AddRegion("pickerBoxRegion", "pickerBoxRegion", x,y,w,h)

	box.pickerBtn = FBButton()
	box.pickerBtn.Caption = name
	box.pickerBtn.picker = picker
	box.pickerBtn.OnClick.Add(_pickerSelect)
	box.SetControl("pickerBoxRegion", box.pickerBtn)



	box.optionBtn.optionBox = box.optionBox = createOptionBox(box)
	box.pickerBtn.box = box.optionBtn.box = box

	awePickerTool.pickerLayout.Add(box, 25, space=2)


def createOptionBox(parentBox):
	'''Creates a layout that holds a Picker's option UI'''

	optionLayout = pyui.FBHBoxLayout()

	addBtn = FBButton()
	addBtn.Caption = "+"
	addBtn.OnClick.Add(_addObjects)
	addBtn.picker = parentBox.picker
	addBtn.Look = FBButtonLook.kFBLookColorChange
	addBtn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.4,0.5,0.3))
	addBtn.SetStateColor(FBButtonState.kFBButtonState1, FBColor(0.35,0.45,0.25))
	optionLayout.AddRelative(addBtn,0.25,height=25, space=4)

	removeBtn = FBButton()
	removeBtn.Caption = "-"
	removeBtn.Look = FBButtonLook.kFBLookColorChange
	removeBtn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.4,0.2,0.5))
	removeBtn.SetStateColor(FBButtonState.kFBButtonState1, FBColor(0.35,0.15,0.45))
	removeBtn.OnClick.Add(_removeObjects)
	removeBtn.picker = parentBox.picker
	optionLayout.AddRelative(removeBtn,0.25,height=25, space=2)

	renameBtn = FBButton()
	renameBtn.Caption = "ab*"
	renameBtn.Look = FBButtonLook.kFBLookColorChange
	renameBtn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.3,0.4,0.5))
	renameBtn.SetStateColor(FBButtonState.kFBButtonState1, FBColor(0.25,0.35,0.45))
	renameBtn.OnClick.Add(_renamePicker)
	renameBtn.picker = parentBox.picker
	renameBtn.pickerButton = parentBox.pickerBtn
	optionLayout.AddRelative(renameBtn,0.25,height=25, space=2)

	deleteBtn = FBButton()
	deleteBtn.Caption = "x"
	deleteBtn.Look = FBButtonLook.kFBLookColorChange
	deleteBtn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.7,0.2,0.3))
	deleteBtn.SetStateColor(FBButtonState.kFBButtonState1, FBColor(0.65,0.15,0.25))
	deleteBtn.OnClick.Add(_deletePicker)
	deleteBtn.picker = parentBox.picker
	deleteBtn.box = parentBox
	optionLayout.AddRelative(deleteBtn,0.25,height=25, space=2)

	return optionLayout

def _addObjects(control,event):
	'''Callback:
	Adds selected objects to the Picker associated with the caller
	'''

	ml = FBModelList()
	FBGetSelectedModels(ml)
	objectList = [o for o in ml]
	control.picker.add(objectList)

def _removeObjects(control,event):
	'''Callback: 
	Removes selected objects from Picker associated with the caller
	'''

	ml = FBModelList()
	FBGetSelectedModels(ml)
	objects = control.picker.objects
	for m in ml:
		if m in objects:
			objects.remove(m)
	control.picker.objects = objects

def _renamePicker(control,event):
	'''Callback:
	Prompts to rename a Picker associated with the caller
	'''

	if control.picker.pickerObject:
		response, value = FBMessageBoxGetUserValue("Rename Picker %s" % control.picker.name, "Name: ", control.picker.name, FBPopupInputType.kFBPopupString, "OK", "Cancel",None,1,True)
		if response == 1:
			if value:
				control.picker.rename(value)
				control.pickerButton.Caption = value
	else:
		FBMessageBox('Picker Error', "Could not locate Picker Object","OK")

def _deletePicker(control,event):
	'''Callback:
	Deletes a Picker and UI associated with caller (and the caller itself)
	'''

	deleteUI = False
	if control.picker.pickerObject:
		result = FBMessageBox("Delete Picker", "Are you sure you want to delete %s" % control.picker.name,"Yes","Cancel")
		if result == 1:
			deleteUI = True
	else:
		deleteUI = True
	if deleteUI:
		control.picker.delete()
		awePickerTool.pickerLayout.Remove(control.box)
		_toolResize()


def _toggleOptionMenu2(control,event):
	'''Callback: 
	Shows a Picker's option UI or hides it, depending on current state
	'''

	region = "pickerBoxRegion"

	# hide options
	if control.box.optionBtn.optionBoxVisible:
		log("hiding optionbox")
		control.box.ClearControl(region)
		control.box.SetControl(region, control.box.pickerBtn)
		control.box.optionBtn.optionBoxVisible = False
		control.box.Refresh(True)
	# show options
	else:
		log("showing optionbox")
		control.box.ClearControl(region)
		control.box.SetControl(region, control.box.optionBox)
		control.box.optionBtn.optionBoxVisible = True
		control.box.Refresh(True)


def _toggleOptionMenu(control,event):

	#if hasattr(awePickerTool,"mouse") and awePickerTool.mouse:

		mouse = QtGui.QCursor.pos()

		#x = int(desktop.width() / 100 * awePickerTool.mouse.PropertyList.Find("X").Data)
		#y = int(desktop.height() / 100 * (100-awePickerTool.mouse.PropertyList.Find("Y").Data))
		x = mouse.x()
		y = mouse.y()

		menu = FBGenericMenu()
		menu.InsertLast("Add Selection",1)
		menu.InsertLast("Remove Selection",2)
		menu.InsertLast("Rename Picker",3)
		menu.InsertLast("Delete Picker",4)

		item = menu.Execute(x,y)

		print item

		if item:
			if item.Id == 1:
				_addObjects(control,None)
			if item.Id == 2:
				_removeObjects(control,None)
			if item.Id == 3:
				_renamePicker(control,None)
			if item.Id == 4:
				_deletePicker(control,None)

		menu.FBDelete()



def _pickerSelect(control,event):
	if control.picker:
		success = control.picker.select()
		if not success:
			FBMessageBox("Picker Error", "An error occured: couldn't find Picker object.\nDeleting this Picker","OK")
			awePickerTool.pickerLayout.Remove(control.box)

	awePickerTool.pickerLayout.HardSelect()

def initPickers(tool):
	log("initializing pickers")
	log("tool", tool)
	tool.pickerLayout.RemoveAll()
	sets = FBSystem().Scene.Sets
	masterSet = None
	for s in sets:
		if s.LongName == "awe:Pickers":
			masterSet = s
	if masterSet:
		hideComponent(masterSet,masterSet.Items)
		for t in masterSet.Items:
			for p in t.Items:
				name = p.PropertyList.Find("PickerName").Data
				objects = [o for o in p.PropertyList.Find("Objects")]
				picker = Picker(name,objects,p)
				createPickerButton(name,picker)


	#_toolResize()
	

	# create the mouse device
#	if hasattr(tool,"mouse") and tool.mouse:
#		try:
#			tool.mouse.FBDelete()
#		except:
#			pass
#	tool.mouse = FBCreateObject("Browsing/Templates/Devices","Mouse","pickerMouse")
#	FBSystem().Scene.Devices.append(tool.mouse)
#	tool.mouse.Live = tool.mouse.Online = True



def hideComponent(component=None,componentList=None):
	disallowedFlags = [FBObjectFlag.kFBFlagBrowsable, FBObjectFlag.kFBFlagRenamable]
	if component:
		for flag in disallowedFlags:
			component.DisableObjectFlags(flag)
	if componentList:
		for c in componentList:
			hideComponent(component=c)


def _pickerObjectDestroyed(object,event):
	object.picker.pickerObject = None


def _toolResize(*args):

	if not awePickerTool:
		return
	log("resizing")
	sb = awePickerTool.scrollBox
	log(sb)
	pl = awePickerTool.pickerLayout
	sX = sb.RegionPosMaxX - sb.RegionPosMinX - 15
	i = childCount = 0
	log("checking children of pickerLayout")
	box = pl.GetChild(i)
	while box:
		log("found picker box %s" % str(i))
		i += 1
		childCount += 1
		box = pl.GetChild(i)

	log("found %d picker boxes" % childCount)
	sY = 27 * childCount + 10
	log("computed size Y: ", sY)
	sb.SetContentSize(sX, sY)


def getUIChildren(control, pList=None, tabs=0, firstRun=True):
	'''Recursively loops through all child UI components of control
	Returns list of items found
	'''
	pList = [] if firstRun else pList
	i = 0
	child = control.GetChild(i)
	if control.ClassName() == "FBScrollBox":
		child = control.Content.GetChild(i)
	log("----"*tabs, control.ClassName(), control.RegionName if control.ClassName() == "FBLayout" else "")
	while child:
		pList.append(child)
		getUIChildren(child, pList,tabs + 1,False)
		i += 1
		child = control.GetChild(i)

	if firstRun:
		return pList


def restructureAll(control,pList=None,firstRun=True):
	'''Recursively loops through all child layouts of control
	and calls Restructure() and Refresh() on them
	'''
	pList = [] if firstRun else pList
	i = 0
	child = control.Content.GetChild(i) if control.ClassName() == "FBScrollBox" else control.GetChild(i)
	if hasattr(control, "Restructure"):
		pList.append(control)
	while child:
		restructureAll(child, pList, False)
		i += 1
		child = control.Content.GetChild(i) if control.ClassName() == "FBScrollBox" else control.GetChild(i)
	if firstRun:
		for c in pList:
			c.Restructure(False)
			c.Refresh(True)
			#log(c)
		pList = []
		

def _fileChange(control,event):
	initPickers(awePickerTool)
	

def _removeSceneCB(control,event):
	FBSystem().Scene.OnChange.RemoveAll()


def _monitorSet(control,event):
	'''Callback:
	Check for manual deletion of a picker object (FBSet).
	If it's the master set, prompt for undo. If it's a picker 
	set, notify the associated Picker object
	'''

	if event.Type == FBSceneChangeType.kFBSceneChangeDetach:
		c = event.ChildComponent
		if c.Is(44) and c.IsSDKComponent():
			if c.LongName == "awe:Pickers":
				FBMessageBox("Picker Error", "Hey! You just deleted the Picker set! Undo that please or I will crash", "OK")
				return
			for p in c.Parents:
				if p.LongName == "awe:Pickers":
					if c.picker:
						c.picker.pickerObject = None



def aweCreateBaseUI(tool):


	# ------------------------------
	# Tool Layout Scheme:
	# 
	# -- MainLayout
	# -- |-- Edit Layout
	# -- |-- |-- Add Button
	# -- |-- ScrollBox
	# -- |-- |-- Picker Layout
	# -- |-- |-- |-- Picker Box
	# -- |-- |-- |-- ...
	# ------------------------------

	startX = 175
	startY = 240


	tool.StartSizeX = startX
	tool.StartSizeY = startY
	tool.OnResize.Add(_toolResize)

	# ----------------------
	# Main Layout 
	# ----------------------
	x = FBAddRegionParam(5,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(5,FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(0,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("mainRegion", "mainRegion",x,y,w,h)

	mainLayout = pyui.FBVBoxLayout()
	tool.SetControl("mainRegion", mainLayout)


	# ----------------------
	# Edit region (top)
	# ----------------------
	x = FBAddRegionParam(20,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(0,FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(35,FBAttachType.kFBAttachNone,"")
	mainLayout.AddRegion("editRegion", "editRegion", x,y,w,h)

	editLayout = pyui.FBHBoxLayout()
	mainLayout.SetControl("editRegion", editLayout)

	addBtn = FBButton()
	addBtn.Caption = "+"
	editLayout.Add(addBtn, 30, space=0, height=30)
	addBtn.OnClick.Add(_createPicker)


	# ----------------------
	# ScrollBox for Picker List
	# ---------------------
	x = FBAddRegionParam(0,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(0,FBAttachType.kFBAttachBottom,"editRegion")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(5,FBAttachType.kFBAttachBottom,"")
	mainLayout.AddRegion("pickerScrollBox", "pickerScrollBox", x,y,w,h)

	tool.scrollBox = FBScrollBox()
	tool.scrollBox.SetContentSize(startX,startY)
	mainLayout.SetControl("pickerScrollBox", tool.scrollBox)
	
	# ----------------------
	# Picker Layout 
	# (child of ScrollBox)
	# ---------------------
	x = FBAddRegionParam(0,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(0,FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(0,FBAttachType.kFBAttachBottom,"")
	tool.scrollBox.Content.AddRegion("pickerRegion", "pickerRegion", x,y,w,h)
	
	tool.pickerLayout = pyui.FBVBoxLayout()
	tool.scrollBox.Content.SetControl("pickerRegion", tool.pickerLayout)


	# clear pickers and rebuild from existing picker objects
	initPickers(tool)

	# add callbacks to scene
	tool.app = FBApplication()
	#tool.app.OnFileNewCompleted.RemoveAll()
	tool.app.OnFileNewCompleted.Add(_fileChange)
	#tool.app.OnFileOpenCompleted.RemoveAll()
	tool.app.OnFileOpenCompleted.Add(_fileChange)
	tool.app.OnFileExit.Add(_removeSceneCB)
	tool.app.OnFileNew.Add(_removeSceneCB)
	tool.app.OnFileOpen.Add(_removeSceneCB)
	FBSystem().Scene.OnChange.Add(_monitorSet)




if __name__ in ['__builtin__', '__main__']:

	awePickerTool = pyui.FBCreateUniqueTool("aweMBPicker")
	aweCreateBaseUI(awePickerTool)