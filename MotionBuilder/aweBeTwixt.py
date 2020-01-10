#	aweBeTwixt for Motionbuilder 2012+
#	TweenKey-functionality + Add/Remove Inbetween
#	written by Awesome A.D.

#	Drag slider or click value buttons to set a keyframe at current time
#	with a weighting towards the previous or next key on all selected models.
#
#	Add/Remove Inbetween: 
#	Ripple following keys forward or backward in time by specified amount
#	of frames. When adding, keyframe on current time are also rippled;
#	when removing, keyframe on current time is left in place. If following
#	keys would overlap left boundary (see option), they are instead capped
#	to frame after boundary.
#	Boundary is Current Time: When removing frames, default boundary is defined
#	to be the previous key from or key on current time. Check this option to set
#	boundary to be the current time instead.
#
#	Both functions operate on selected models on a per-FCurve basis (i.e. individually
#	on each animated channel)


from pyfbsdk import *
import pyfbsdk_additions as pyui
import bisect as bi

def aweGetFCurves(pAnimationNode, pList):
	'''Get a list of FCurves attached to the model via its animationNode

	'''
	
	# Call this function by passing in the model's top AnimationNode and 
	# an empty list (by reference); the function will recursively traverse 
	# the hierarchy and gather all FCurves into the list provided by the 
	# second parameter (pList).
	# Thus, this function does not return a result, rather it populates
	# the list provided in the second parameter.

	fcurve = pAnimationNode.FCurve
	if fcurve:
		pList.append(fcurve)
	else:
		for node in pAnimationNode.Nodes:
			aweGetFCurves(node, pList)

def aweGetCurveList():
	'''Generates list of all fCurves on all selected objects

	'''
	ml = FBModelList()
	FBGetSelectedModels(ml)
	for m in ml:
		fcList = []
		aweGetFCurves(m.AnimationNode,fcList)
		for c in fcList:
			yield c


def aweGetKeyBounds(pFCurve):
	'''Finds the previous and next key from the current time

	'''

	# Returns the times (in frames) at which the previous and next
	# keys can be found.
	# Returns None if there is no key previous or after the current time.

	keyTimes = [k.Time.GetFrame() for k in pFCurve.Keys]
	currentTime = FBSystem().LocalTime.GetFrame()

	leftBoundary = bi.bisect_left(keyTimes, currentTime) - 1
	rightBoundary = bi.bisect_right(keyTimes, currentTime)
	
	if leftBoundary >= rightBoundary or leftBoundary < 0 or rightBoundary >= len(keyTimes):
		return None
	else:
		return [keyTimes[leftBoundary], keyTimes[rightBoundary]]


def aweGetNextKeys(pFCurve):
	'''Returns list of all keys after (and/not including) current time

	'''

	if len(pFCurve.Keys) == 0:
		return None, None
	keys = []
	keyTimes = []
	leftBoundary = None
	currentTime = FBSystem().LocalTime.GetFrame()
	for k in range(len(pFCurve.Keys)):
		key = pFCurve.Keys[k]
		kt = key.Time.GetFrame()
		keyTimes.append(kt)
		if kt >= currentTime:
			keys.append(key)
		if kt == currentTime:
			leftBoundary = k
	if not leftBoundary:
		leftBoundary = bi.bisect_left(keyTimes, currentTime) - 1
	return keys, pFCurve.Keys[leftBoundary]  


def aweBlendValue(pFCurve, pPrevious, pNext, pWeight = 0.5):
	'''Calculates a new value by weighting the values of the previous and next keys

	'''

	# pPrevious and pNext are time values (as frames) representing the boundaries
	# pWeight is a value between 0.0 and 1.0 used to calculate the result (defaults to .5 if not given)
	# Returns a single new value

	t = FBTime()
	t.SetFrame(pPrevious)
	pValue = pFCurve.Evaluate(t)
	t.SetFrame(pNext)
	nValue = pFCurve.Evaluate(t)
	return pWeight * (nValue - pValue) + pValue


def aweTween(pWeight):
	'''Does the works
	Iterates over each selected model and tweens according to weight

	'''
	pc = FBPlayerControl()
	for curve in aweGetCurveList():
		keyBounds = aweGetKeyBounds(curve)
		if keyBounds:
			# calculate linear interpolated value at blended time
			blendValue = aweBlendValue(curve, keyBounds[0], keyBounds[1], pWeight)
			# this ensures the scene view is updated while the value is keyed in
			pc.Key()
			###curve.KeyDelete(FBSystem().LocalTime, FBSystem().LocalTime)
			k = curve.KeyAdd(FBSystem().LocalTime, blendValue)
            if k > 0:
                thisKey = curve.Keys[k]
                prevKey = curve.Keys[k-1]
                thisKey.Interpolation = prevKey.Interpolation


def aweInbetween(pCount,pBoundary="key"):
	'''Adds or removes frames between keys

	'''

	# Ruleset:
	# 1) Adding frames always allowed; if key on current time, key also gets shifted
	# Removing frames:
	# 2) if key on current time, key is ignored
	# 3) prevent overlap of keys: following keys must not shift left of boundary (key
	#    or current time); onOverlap: cap shift count so following key = boundary + 1

	currentTime = FBSystem().LocalTime.GetFrame()
	for curve in aweGetCurveList():
		keys, boundary = aweGetNextKeys(curve)
		boundary = boundary if pBoundary == "key" else FBTime().SetFrame(currentTime)
		shiftCount = pCount
		if keys:
			# start from last key if adding frames
			# there's a weird bug if the first key gets shifted beyond the second key
			# e.g. [10,13,18] -> + 5 *should be* [15,18,23] *actually becomes* [15,15,23]
			if pCount > 0:
				keys.reverse()
			for key in keys:
				newTime = key.Time.GetFrame() + shiftCount
				
				# 2)
				if pCount < 0 and boundary.Time.GetFrame() == key.Time.GetFrame():
					continue

				# 3)
				if pCount < 0 and newTime <= boundary.Time.GetFrame():				
					while key.Time.GetFrame() + shiftCount <= boundary.Time.GetFrame():
						shiftCount += 1
					newTime = key.Time.GetFrame() + shiftCount

				t = FBTime()
				t.SetFrame(newTime)
				key.Time = t


## =============================
## UI & Callbacks
## =============================


def aweSliderDrag(control,event):
	'''Callback for slider drag event (onChange)'''

	value = float(control.Value) / 100.0
	aweTween(value)
	tool = pyui.FBToolList["aweBeTwixt"]
	if tool:
		tool.label.Caption = str(int(control.Value))


def aweSliderDrop(control,event):
	'''Callback for slider drop event (onTransaction->false)'''

	if not event.IsBeginTransaction:
		control.Value = 50
		tool = pyui.FBToolList["aweBeTwixt"]
		if tool:
			tool.label.Caption = "50"


def aweTweenBtnClick(button,event):
	value = float(button.Caption) / 100.0
	aweTween(value)

def aweInbetweenBtnClick(button,event):
	value = int(button.Caption)
	tool = pyui.FBToolList["aweBeTwixt"]
	boundary = "key"
	if tool:
		if tool.boundaryCB.State:
			boundary = "currentTime"
	aweInbetween(value,boundary)



def aweCreateTool(pToolName):
	'''Creates tool (layout), adds UI controls, adds to ToolManager'''
    
	# create Tool
	tool = pyui.FBCreateUniqueTool(pToolName)

	# initial settings
	tool.StartSizeX = 316
	tool.StartSizeY = 175
	tool.MinSizeX = 316
	tool.MinSizeY = 175
	tool.MaxSizeX = 316
	tool.MaxSizeY = 175


	# value label
	x = FBAddRegionParam(0,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(5,FBAttachType.kFBAttachTop,"")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(20,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("labelLayout","labelLayout", x, y, w, h)

	labelLayout = pyui.FBHBoxLayout()
	tool.SetControl("labelLayout", labelLayout)

	tool.label = FBLabel()
	tool.label.Caption = "50"
	tool.label.BorderStyle = FBBorderStyle.kFBPickingBorder
	tool.label.Justify = FBTextJustify.kFBTextJustifyCenter

	labelLayout.Add(tool.label, 304, height=20)


	# slider region/control
	x = FBAddRegionParam(5,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(20,FBAttachType.kFBAttachTop,"labelLayout")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(50,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("sliderRegion","sliderRegion", x, y, w, h)

	sliderLayout = pyui.FBHBoxLayout()
	tool.SetControl('sliderRegion', sliderLayout)

	hs = FBSlider()    
	hs.Orientation = FBOrientation.kFBHorizontal 
	hs.Hint = "Drag and Release at desired value"  
	hs.Min = 0
	hs.Max = 100
	hs.Value = 50
	hs.SmallStep = 1
	hs.LargeStep = 10 

	# callbacks
	hs.OnChange.Add(aweSliderDrag)
	hs.OnTransaction.Add(aweSliderDrop)

	# add to region
	sliderLayout.Add(hs, 296, height=18)


	# buttons region/controls
	x = FBAddRegionParam(8,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(30,FBAttachType.kFBAttachTop,"sliderRegion")
	w = FBAddRegionParam(5,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(50,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("btnRegion","btnRegion", x, y, w, h)

	buttonLayout = pyui.FBHBoxLayout()
	tool.SetControl('btnRegion', buttonLayout)

	for i in range(0,11):
		btn = FBButton()
		btn.BorderStyle = FBBorderStyle.kFBNoBorder
		btn.Look = FBButtonLook.kFBLookColorChange
		if i > 0 and i < 5:
			btn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.2,0.3,0.4))
		elif i > 5 and i < 10:
			btn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.4,0.2,0.3))
		else:
			btn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.2,0.2,0.2))
		btn.Caption = str(i*10)
		btn.OnClick.Add(aweTweenBtnClick)
		buttonLayout.Add(btn, 26,space=2, height=30)

	
	# Inbetween label
	x = FBAddRegionParam(6,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(40,FBAttachType.kFBAttachTop,"btnRegion")
	w = FBAddRegionParam(0,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(20,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("inbetweenLabelRegion","inbetweenLabelRegion", x, y, w, h)

	inbetweenLabelLayout = pyui.FBHBoxLayout()
	tool.SetControl("inbetweenLabelRegion", inbetweenLabelLayout)

	iblabel = FBLabel()
	iblabel.Caption = "Add / Remove Inbetween"
	iblabel.BorderStyle = FBBorderStyle.kFBPickingBorder
	iblabel.Justify = FBTextJustify.kFBTextJustifyCenter

	inbetweenLabelLayout.Add(iblabel, 316, height=20)

	# inbetween buttons
	x = FBAddRegionParam(6,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(20,FBAttachType.kFBAttachTop,"inbetweenLabelRegion")
	w = FBAddRegionParam(5,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(30,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("ibBtnRegion","ibBtnRegion", x, y, w, h)

	ibButtonLayout = pyui.FBHBoxLayout()
	tool.SetControl('ibBtnRegion', ibButtonLayout)

	for i in range(-5,5):
		btn = FBButton()
		btn.Look = FBButtonLook.kFBLookColorChange
		if i >= 0:
			btn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.2,0.3,0.4))
		else:
			btn.SetStateColor(FBButtonState.kFBButtonState0, FBColor(0.4,0.2,0.3))
		c = str(i) if i < 0 else "+" + str(i+1)
		btn.Caption = c
		btn.OnClick.Add(aweInbetweenBtnClick)
		ibButtonLayout.Add(btn, 28,space=3, height=30)

	# option checkbox
	x = FBAddRegionParam(8,FBAttachType.kFBAttachLeft,"")
	y = FBAddRegionParam(30,FBAttachType.kFBAttachTop,"ibBtnRegion")
	w = FBAddRegionParam(-8,FBAttachType.kFBAttachRight,"")
	h = FBAddRegionParam(0,FBAttachType.kFBAttachBottom,"")
	tool.AddRegion("cbRegion","cbRegion", x, y, w, h)

	tool.boundaryCB = FBButton()
	tool.boundaryCB.Caption = "Boundary is Current Time"
	tool.boundaryCB.Style = FBButtonStyle.kFBCheckbox
	tool.boundaryCB.Hint = "Remove inbetween: The left boundary when shifting keys is\nthe previous key (default) or the current time (checked)"
	tool.SetControl("cbRegion", tool.boundaryCB)

	return tool



if __name__ in ['__builtin__', '__main__']:
	
	toolName = "aweBeTwixt"	
	tool = aweCreateTool(toolName)


