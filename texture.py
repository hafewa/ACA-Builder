# 作者：willimxp
# 所属插件：ACA Builder
# 功能概述：
#   对象展UV和贴材质
import bpy
import bmesh
import math
from mathutils import Vector

from . import utils
from .const import ACA_Consts as con
from .data import ACA_data_obj as acaData
from .data import ACA_data_template as tmpData

# 展UV的类型
class uvType:
    CUBE = 'cube'
    SCALE = 'scale'
    FIT = 'fit'
    RESET = 'reset'
    CYLINDER  = 'cylinder'
    WIN = 'win'



# 二维点阵基于p点的缩放
# v：待缩放的向量（vx，vy）
# s: 缩放比例（sx，sy）
# p：缩放的原点（px，py）
def __Scale2D( v, s, p ):
    return ( p[0] + s[0]*(v[0] - p[0]), p[1] + s[1]*(v[1] - p[1]) )     

# UV的缩放
def __ScaleUV( uvMap, scale, pivot, fixcenter=False):
    for uvIndex in range( len(uvMap.data) ):
        if fixcenter:
            if uvMap.data[uvIndex].uv[0] > - 0.0001 and uvMap.data[uvIndex].uv[0]< 1.0001:
                continue
        uvMap.data[uvIndex].uv = __Scale2D( uvMap.data[uvIndex].uv, scale, pivot )

# 二维点阵的旋转
def __make_rotation_transformation(angle, origin=(0, 0)):
    from math import cos, sin
    cos_theta, sin_theta = cos(angle), sin(angle)
    x0, y0 = origin    
    def xform(point):
        x, y = point[0] - x0, point[1] - y0
        return (x * cos_theta - y * sin_theta + x0,
                x * sin_theta + y * cos_theta + y0)
    return xform

# UV的旋转
def __RotateUV(uvMap, angle, pivot):
    rot = __make_rotation_transformation(angle, pivot)
    for uvIndex in range( len(uvMap.data) ):
        uvMap.data[uvIndex].uv = rot(uvMap.data[uvIndex].uv ) 
    return

# 复制UV
def __copyUV(
    fromObj:bpy.types.Object,
    toObj:bpy.types.Object):
    # 从资产中传递预定义的UV
    # 确认选中两个对象
    fromobjCopy = utils.copySimplyObject(fromObj,singleUser=True)
    fromobjCopy.select_set(True)
    toObj.select_set(True)
    bpy.context.view_layer.objects.active = fromobjCopy
    # 获取源UV
    uv = fromobjCopy.data.uv_layers[0]
    uv.active = True
    # 重建目标UV
    toObj.data.uv_layers.remove(toObj.data.uv_layers[0])
    new_uv = toObj.data.uv_layers.new(name='UVMap')
    new_uv.active = True
    # 调用UV传递
    bpy.ops.object.join_uvs()

    # 删除fromObj
    bpy.data.objects.remove(fromobjCopy)

    return

# 展UV，提供了多种不同的方式
def UvUnwrap(object:bpy.types.Object,
             type=None,
             scale=None,
             pivot=(0,0),
             rotate=None,
             fitIndex=None,
             cubesize=2,
             correctAspect = True,
             scaleToBounds = False,
             remainSelect = False
             ):   
    # 隐藏对象不重新展UV
    if (object.hide_viewport 
        or object.hide_get()
        ):
        return

    # 聚焦对象
    utils.focusObj(object)

    # 应用modifier
    utils.applyAllModifer(object)

    # 进入编辑模式
    bpy.ops.object.mode_set(mode = 'EDIT') 
    bpy.ops.mesh.select_mode(type = 'FACE')
    if not remainSelect:
        bpy.ops.mesh.select_all(action='SELECT')

    # 验证对象是否可以展UV，至少应该有一个以上的面
    bm = bmesh.new()
    bm.from_mesh(object.data)
    faceCount= len(bm.faces)
    bm.free()
    if faceCount == 0 : 
        bpy.ops.object.mode_set(mode = 'OBJECT')
        return
    
    if type == None:
        # 默认采用smart project
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(66), 
            margin_method='SCALED', 
            island_margin=0.0001, 
            area_weight=0.0, 
            correct_aspect=True, 
            scale_to_bounds=False
        )
    # 普通材质的cube project，保证贴图缩放的一致性
    elif type == uvType.CUBE:
        bpy.ops.uv.cube_project(
            cube_size=cubesize,
            correct_aspect=correctAspect,
            scale_to_bounds=scaleToBounds,
        )
    # 精确适配
    # 先所有面一起做加权分uv，然后针对需要特殊处理的面，进行二次适配
    elif type == uvType.FIT:
        # 先做一次加权投影
        bpy.ops.uv.cube_project(
            scale_to_bounds=True
        )
        # 清空选择
        bpy.ops.mesh.select_all(action = 'DESELECT')
        # 载入bmesh
        me = object.data
        bm = bmesh.from_edit_mesh(me)
        # 选择面
        for face in bm.faces:
            if face.index in fitIndex:
                face.select = True 
        # 写回对象
        bmesh.update_edit_mesh(me)
        # unwarp
        bpy.ops.uv.cube_project(
            scale_to_bounds=True
        )
    # 重置UV，让每个面都满铺，但存在rotate的问题，暂未使用
    elif type == uvType.RESET:
        bpy.ops.uv.reset()
    # 柱状投影，在柱子上效果很好
    elif type == uvType.CYLINDER:
        bpy.ops.uv.cylinder_project(
            direction='ALIGN_TO_OBJECT',
            align='POLAR_ZY',
            scale_to_bounds=True
        )
    bpy.ops.object.mode_set(mode = 'OBJECT')

    # 拉伸UV，参考以下：
    # https://blender.stackexchange.com/questions/75061/scale-uv-map-script
    if scale != None:
        uvMap = object.data.uv_layers['UVMap']
        __ScaleUV(uvMap,scale,pivot)

    # 旋转UV，参考：
    # https://blender.stackexchange.com/questions/28929/rotate-uv-by-specific-angle-e-g-30deg-in-python-script-in-backgroud-mode
    if rotate != None:
        uvMap = object.data.uv_layers['UVMap']
        __RotateUV(uvMap,rotate,pivot)

    return

# 设置材质，并进行相应几何处理
def setMat(object:bpy.types.Object,
              mat:bpy.types.Object,
              override=False,
              single=False):
    # 非mesh对象直接跳过
    if object == None: return
    if object.type not in ('MESH','CURVE'):
        return
    
    # 如果已经有材质，且未声明override，则不做材质
    if object.active_material != None \
        and not override:
        # 不做任何改变
        return
    
    aData:tmpData = bpy.context.scene.ACA_temp

    # 简单平铺的材质
    if mat in (
        aData.mat_wood,         # 木材材质
        aData.mat_rock,         # 石材材质
        aData.mat_stone,        # 石头材质
        aData.mat_red,          # 漆.土朱材质
        aData.mat_brick_1,      # 方砖缦地
        aData.mat_brick_2,      # 条砖竖铺
        aData.mat_brick_3,      # 条砖横铺
        aData.mat_dust_red,     # 抹灰.红
        aData.mat_gold,         # 漆.金
    ):
        __setTileMat(object,
                     mat,
                     uvType=uvType.CUBE,
                     cubesize=2)

    # 看面平铺的材质
    if mat in (
        aData.mat_paint_cloud,      # 挑檐枋工王云
        aData.mat_paint_walkdragon, # 平板枋走龙
    ):
        object = __setBoardFang(object,mat)
    
    # 拉伸填充的材质
    if mat in (
        aData.mat_paint_doorring,   # 隔扇绦环
        aData.mat_paint_door,       # 隔扇壶门
    ):
        __setTileMat(object,
                     mat,
                     uvType=uvType.CUBE,
                     scaleToBounds=True)
    
    # 梁枋彩画
    if mat in (
        aData.mat_paint_beam_big,
        aData.mat_paint_beam_small,
    ):
        __setFangMat(object,mat)

    # 由额垫板，公母草贴图
    if mat == aData.mat_paint_grasscouple:
        object = __setYOUE(object,mat)

    # 三交六椀隔心
    if mat == aData.mat_geshanxin:
        __setTileMat(object,
                     mat,
                     uvType=uvType.CUBE,
                     cubesize=0.1)

    # 柱头贴图
    if mat == aData.mat_paint_pillerhead:
        object = __setPillerHead(object,mat)

    # 栱垫板
    if mat == aData.mat_paint_dgfillboard:
        object = __setDgBoard(object,mat)

    # 檐椽
    if mat == aData.mat_paint_rafter:
        object = __setRafterMat(object,mat)
    
    # 飞椽
    if mat == aData.mat_paint_flyrafter:
        object = __setFlyrafterMat(object,mat)
    
    # 望板
    if mat == aData.mat_paint_wangban:
        __setWangban(object,mat)

    # 子角梁，龙肚子
    if mat == aData.mat_paint_ccb:
        __setCCB(object,mat)

    # 山花板
    if mat == aData.mat_paint_shanhua:
        __setShanhua(object,mat)
        pass

    return object

# 拷贝目标对象的材质
# 复制所有材质
def __copyMaterial(fromObj:bpy.types.Object,
                 toObj:bpy.types.Object,
                 single=False):
    if toObj.type in ('MESH','CURVE'):
        toObj.data.materials.clear()
        for mat in fromObj.data.materials:
            if single:
                mat = mat.copy()
            toObj.data.materials.append(mat)

    return

# 设置材质的输入参数
# https://blender.stackexchange.com/questions/191183/changing-a-value-node-in-many-materials-with-a-python-script
def __setMatValue(mat:bpy.types.Material,
                inputName:str,
                value):
    if mat is not None and mat.use_nodes and mat.node_tree is not None:
        for node in mat.node_tree.nodes:
            for input in node.inputs:
                if input.name == inputName and input.type == 'VALUE':
                    input.default_value = value 
    return

# 设置对象使用的材质编号
def __setMatByID(
        object:bpy.types.Object,
        id=0,
):
    bm = bmesh.new()
    bm.from_mesh(object.data)
    for face in bm.faces:
        face.material_index = id
    bm.to_mesh(object.data)
    bm.free()
    return

# 平铺材质
def __setTileMat(
        object:bpy.types.Object,
        mat:bpy.types.Object,
        single=False,
        uvType=uvType.CUBE,
        cubesize=2,
        correctAspect = True,
        scaleToBounds = False,
):
    # 绑定材质
    __copyMaterial(mat,object,single)

    # 平铺类材质默认使用Cube Projection
    # 也可以传入希望的uv方式
    UvUnwrap(object,
             uvType,
             cubesize=cubesize,
             correctAspect=correctAspect,
             scaleToBounds=scaleToBounds)
    
    return

# 檐椽展UV
def __setRafterMat(rafter:bpy.types.Object,mat):
    # 绑定檐椽材质
    __copyMaterial(mat,rafter)

    # 拆分，将合并或array的椽子，拆分到独立的对象
    rafterList = utils.separateObject(rafter)
    # 逐一处理每根椽子
    for n in range(len(rafterList)):
        rafter = rafterList[n]
        # 找到端头面
        bm = bmesh.new()
        bm.from_mesh(rafter.data)
        bm.faces.ensure_lookup_table()
        # 轮询面集合，查找最大值
        headPoint = Vector((0,0,0))
        endFaceIndex = 0
        for face in bm.faces:
            # 面的几何中心点
            faceCenter = face.calc_center_median()
            if faceCenter.x > headPoint.x:
                headPoint = faceCenter
                endFaceIndex = face.index
        # 端头材质绑定
        if n%2 == 1 :
            # 正常色（绿）
            bm.faces[endFaceIndex].material_index = 1
        else:
            # 异色（青）
            bm.faces[endFaceIndex].material_index = 2
        # 选中并展UV
        bm.faces[endFaceIndex].select = True
        bm.to_mesh(rafter.data)
        bm.free()
    # 端头按scale展开
    bpy.ops.object.mode_set(mode = 'EDIT') 
    bpy.ops.uv.cube_project(
        scale_to_bounds=True
    )
    bpy.ops.object.mode_set(mode = 'OBJECT')

    # 重新合并，以免造成混乱
    rafter = utils.joinObjects(rafterList)
    return rafter

# 飞椽展UV
def __setFlyrafterMat(flyrafter:bpy.types.Object,mat):
    # 绑定飞椽材质
    __copyMaterial(mat,flyrafter)

    # 拆分，将合并或array的椽子，拆分到独立的对象
    flyrafterList = utils.separateObject(flyrafter)
    # 逐一处理每根椽子
    for n in range(len(flyrafterList)):
        flyrafter = flyrafterList[n]
        # 找到端头面
        bm = bmesh.new()
        bm.from_mesh(flyrafter.data)
        bm.faces.ensure_lookup_table()
        # 轮询面集合，查找最大值
        headPoint = Vector((0,0,0))
        endFaceIndex = 0
        for face in bm.faces:
            # 面的几何中心点
            faceCenter = face.calc_center_median()
            if faceCenter.x > headPoint.x:
                headPoint = faceCenter
                endFaceIndex = face.index
        # 端头材质绑定
        bm.faces[endFaceIndex].material_index = 1
        # 选中并展UV
        bm.faces[endFaceIndex].select = True
        bm.to_mesh(flyrafter.data)
        bm.free()
    # 端头用reset方式，可以适配椽头菱形的变形
    bpy.ops.object.mode_set(mode = 'EDIT') 
    bpy.ops.uv.reset()
    bpy.ops.object.mode_set(mode = 'OBJECT')

    # 重新合并，以免造成混乱
    flyrafter = utils.joinObjects(flyrafterList)

    return flyrafter

# 计算柱头贴图的高度
# 依据大额枋、由额垫板、小额枋的高度计算
def __setPillerHead(pillerObj:bpy.types.Object,
                    mat:bpy.types.Object):
    buildingObj = utils.getAcaParent(
        pillerObj,con.ACA_TYPE_BUILDING)
    bData:acaData = buildingObj.ACA_data
    aData:tmpData = bpy.context.scene.ACA_temp
    dk = bData.DK

    # 为了使用静态的PBR贴图的同时，动态的控制柱头贴图高度    
    # 将柱子分为上中下分别裁切、拼接    
    # 柱身对象
    pillerBodyObj = utils.copySimplyObject(
        pillerObj,singleUser=True)
    # 柱头对象
    pillerHeadObj = utils.copySimplyObject(
        pillerObj,singleUser=True)
    # 柱顶对象
    pillerTopObj = utils.copySimplyObject(
        pillerObj,singleUser=True)
    pillerParts=[]
    pillerParts.append(pillerBodyObj)
    pillerParts.append(pillerHeadObj)
    pillerParts.append(pillerTopObj)
    
    # 刷新，否则出现柱头计算错误
    utils.updateScene()

    # 计算柱头高度（大额枋/小额枋下皮）
    fangHeight = con.EFANG_LARGE_H*dk
    if bData.use_smallfang:
        fangHeight += (con.BOARD_YOUE_H*dk
            + con.EFANG_SMALL_H*dk)
    # 裁切柱头
    pCut = pillerObj.matrix_world @ Vector((
        0,0,pillerObj.dimensions.z-fangHeight))
    utils.addBisect(
        object=pillerBodyObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_inner=True,
        direction='Y',
        use_fill=False,
    )
    utils.addBisect(
        object=pillerHeadObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_outer=True,
        direction='Y',
        use_fill=False,
    )

    # 裁切柱顶（剪掉顶面，只保留圆筒形状，做贴图）
    pCut = pillerObj.matrix_world @ Vector((
        0,0,pillerObj.dimensions.z-0.02))
    utils.addBisect(
        object=pillerTopObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_outer=True,
        direction='Y',
        use_fill=False,
    )
    utils.addBisect(
        object=pillerHeadObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_inner=True,
        direction='Y',
        use_fill=False,
    )

    # 绑定柱头材质
    __copyMaterial(mat,pillerHeadObj)
    __copyMaterial(aData.mat_red,pillerBodyObj)
    __copyMaterial(aData.mat_red,pillerTopObj)
    # 重新展UV
    UvUnwrap(pillerHeadObj,uvType.CYLINDER)
    UvUnwrap(pillerBodyObj,uvType.CUBE,cubesize=2)
    UvUnwrap(pillerTopObj,uvType.CUBE,cubesize=2)
    # 旋转45度，让金龙面对前方
    pillerHeadObj.rotation_euler.z = math.radians(45)

    # 表面平滑
    for part in pillerParts:
        utils.shaderSmooth(part)
    # 移除原有的柱身，并将柱名称让给新对象
    pillerName = pillerObj.name
    bpy.data.objects.remove(pillerObj)
    # 柱身、柱头合并
    newPiller = utils.joinObjects(pillerParts,pillerName,cleanup=True)
    
    return newPiller

# 已废弃，栱垫板改为PBR模式，改用__setDgBoard方法
# # 设置垫拱板的重复次数，根据斗栱攒数计算
# def __setDgCount(object:bpy.types.Object):
#     # 载入数据
#     buildingObj = utils.getAcaParent(
#         object,con.ACA_TYPE_BUILDING)
#     bData:acaData = buildingObj.ACA_data

#     # 设置材质中的斗栱攒数
#     fang_length = object.dimensions.x
#     count = round(fang_length / bData.dg_gap)
#     __setMatValue(
#         mat=object.active_material,
#         inputName='count',
#         value=count)
    
# 判断枋子使用的AB配色
def __setFangMat(fangObj:bpy.types.Object,
                 mat:bpy.types.Object):
    # 根据开间位置的尺寸，选择不同的matID
    # 0-XL、1-L、2-M、3-S、4-异色XL、5-异色L、6-异色M、7-异色S
    matID = 0
    
    # 分解获取柱子编号
    fangID = fangObj.ACA_data['fangID']
    setting = fangID.split('#')
    pFrom = setting[0].split('/')
    pFrom_x = int(pFrom[0])
    pFrom_y = int(pFrom[1])
    pTo = setting[1].split('/')
    pTo_x = int(pTo[0])
    pTo_y = int(pTo[1])

    # 计算为第几间？
    buildingObj = utils.getAcaParent(fangObj,con.ACA_TYPE_BUILDING)
    bData:acaData = buildingObj.ACA_data
    # 前后檐
    if pFrom_y == pTo_y:
        roomIndex = (pFrom_x+pTo_x-1)/2
        n = int((bData.x_rooms+1)/2)%2
    # 两山
    elif pFrom_x == pTo_x:
        roomIndex = (pFrom_y+pTo_y-1)/2
        n = int((bData.y_rooms+1)/2)%2

    ''' 根据n来判断是否是明间,比如，
    5间时,奇数间(1,3,5)应该用正色
    7间时,偶数间(2,4,6)应该用正色'''
    if roomIndex%2 == n:
        matID = 4
    else:
        matID = 0

    # 判断额枋长度
    fangLength = fangObj.dimensions.x
    if fangLength < 1.8:
        # 超短款
        matID += 3
    elif fangLength < 2.8:
        # 短款
        matID += 2
    elif fangLength < 5:
        # 中款
        matID += 1

    # 绑定材质
    __copyMaterial(fromObj=mat,toObj=fangObj)
    # 选择slot
    __setMatByID(fangObj,matID)
    # 展UV
    UvUnwrap(fangObj,
             uvType.CUBE,
             scaleToBounds=True)

    # 设置槫头坐龙
    if (fangObj.name.startswith('挑檐桁')
        or fangObj.name.startswith('正心桁')):
        __setTuanHead(fangObj)
    
    return

# 设置槫头坐龙
def __setTuanHead(tuan:bpy.types.Object):
    # 追加槫头坐龙材质
    aData:tmpData = bpy.context.scene.ACA_temp
    matHeadDragon = aData.mat_paint_tuanend.active_material
    tuan.data.materials.append(matHeadDragon)
    matIndex = len(tuan.material_slots)-1

    # 找到左右两个端头，并绑定新材质
    bm = bmesh.new()
    bm.from_mesh(tuan.data)
    for face in bm.faces:
        face.select = False

    # 以底面可确定的0号面为参考
    rightNormal = Vector((1,0,0))
    leftNormal = Vector((-1,0,0))
    # 选择法线类似的所有面，0.1是在blender里尝试的经验值
    for face in bm.faces:
        right:Vector = face.normal - rightNormal
        left:Vector = face.normal - leftNormal
        if right.length < 1 or left.length < 1:
            face.material_index = matIndex
    bm.to_mesh(tuan.data)
    bm.free()

    # 从资产中传递预定义的UV
    __copyUV(
        fromObj=aData.mat_paint_tuanend,
        toObj= tuan,
    )
    return

# 设置由额垫板公母草贴图
# 由额垫板贴图采用三段式，中间为横向平铺的公母草，两端为箍头
# 按照箍头、公母草贴图的XY比例，计算公母草的横向平铺次数
def __setYOUE(youeObj:bpy.types.Object,
              mat:bpy.types.Object):
    # 使用垫板模版替换原对象
    youeNewObj = utils.copyObject(mat,singleUser=True)
    utils.replaceObject(youeObj,youeNewObj,delete=True)
    
    # 2、选择中段
    utils.focusObj(youeNewObj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    # 选择中段中段控制采用了对象的vertex group
    vertex_group_name = 'body'  # 在模版中预定义的vertex group名称
    youeNewObj.vertex_groups.active = \
        youeNewObj.vertex_groups[vertex_group_name]
    bpy.ops.object.vertex_group_select()

    # 3、中段的mesh缩放
    a = 0.463       # 箍头长度
    l1 = mat.dimensions.x
    l2 = youeNewObj.dimensions.x
    x1 = l1 - a*2
    x2 = l2 - a*2
    scale = (x2/l2)/(x1/l1)
    bpy.ops.transform.resize(
        value=(scale,1,1))
    
    # 4、退出编辑状态，以便后续获取uvmap
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 5、中段的UV缩放
    b = 1.737       # 中段长度
    c = 3           # 模版中的默认重复次数
    scale = round(x2/b)/c
    uvMap = youeNewObj.data.uv_layers['UVMap']
    # 这里用fixcenter的方式，避免影响箍头的uv（箍头UV预定义为满铺）
    # vertex group无法直接传递给uvmap，因为uvmap对应到面（faceloop）
    # 一个vertex可能对应对个uv
    __ScaleUV(uvMap,scale=(scale,1),pivot=(0.5,0.5),fixcenter=True)
    
    return youeNewObj

# 栱垫板贴图
def __setDgBoard(dgBoardObj:bpy.types.Object,
                 mat:bpy.types.Object):
    # 载入数据
    buildingObj = utils.getAcaParent(
        dgBoardObj,con.ACA_TYPE_BUILDING)
    bData:acaData = buildingObj.ACA_data
    
    # 计算斗栱攒数
    totalLength = dgBoardObj.dimensions.x
    # 补偿float精度
    totalLength += 0.001
    # 向下取整，宜疏不宜密（与builddougong.__buildDougong方法统一）
    count = math.floor(totalLength/bData.dg_gap)
    boardLength = totalLength/count

    # 在每攒斗栱之间摆放栱垫板
    newDgBoardList = []
    for n in range(count):
        newDgBoard = utils.copySimplyObject(mat)
        # 适配原栱垫板的尺寸（可能斗口不同）
        newDgBoard.dimensions = (
            boardLength,
            dgBoardObj.dimensions.y,
            dgBoardObj.dimensions.z)
        # 后续会将新的栱垫板替换旧的栱垫板
        # 所以location应该是相对旧的栱垫板的定位
        # 所以y=z=0
        newDgBoard.location.x = (
            (n+0.5)*boardLength-totalLength/2)
        newDgBoard.location.y = 0
        newDgBoard.location.z = 0
        utils.applyTransfrom(newDgBoard,use_scale=True)
        newDgBoardList.append(newDgBoard)

    # 合并栱垫板
    joinedDgBoard = utils.joinObjects(newDgBoardList)
    utils.applyTransfrom(joinedDgBoard,use_location=True)
    utils.replaceObject(
        dgBoardObj,
        joinedDgBoard,
        delete=True)

    return joinedDgBoard

# 设置挑檐枋工王云、平板枋走龙贴图
def __setBoardFang(fangObj:bpy.types.Object,
                   mat:bpy.types.Object):
    # 复制材质库中的工王云，走龙贴图
    # 这些贴图的slot0为彩画，slot1为纯色大青
    __copyMaterial(mat,fangObj)

    # 找到顶面和底面，做材质slot1的大青
    bm = bmesh.new()
    bm.from_mesh(fangObj.data)
    # -Z轴为向量比较基准
    negZ = Vector((0,0,-1))
    # 选择法线类似的所有面，0.1是在blender里尝试的经验值
    for face in bm.faces:
        # 根据向量的点积判断方向，正为同向，0为垂直，负为反向
        dir = face.normal.dot(negZ)
        if abs(dir) > 0:
            # 设置为slot1的大青
            face.material_index = 1
    bm.to_mesh(fangObj.data)
    bm.free()

    # 更新UV，适配对象高度的满铺
    cubeHeight = fangObj.dimensions.z
    UvUnwrap(fangObj,
             type=uvType.CUBE,
             cubesize=cubeHeight)
    return fangObj

# 望板材质，底面刷红
def __setWangban(wangban:bpy.types.Object,
                 mat:bpy.types.Object):
    __copyMaterial(mat,wangban)

    # 找到所有的底面
    bm = bmesh.new()
    bm.from_mesh(wangban.data)
    # -Z轴为向量比较基准
    negZ = Vector((0,0,-1))
    # 选择法线类似的所有面，0.1是在blender里尝试的经验值
    for face in bm.faces:
        # 根据向量的点积判断方向，正为同向，0为垂直，负为反向
        dir = face.normal.dot(negZ)
        if dir > 0:
            # 设置为slot1的红漆
            face.material_index = 1
    bm.to_mesh(wangban.data)
    bm.free()

    # 展UV
    UvUnwrap(wangban,uvType.CUBE)
    return

# 设置仔角梁龙肚子
def __setCCB(ccbObj:bpy.types.Object,
             mat:bpy.types.Object):
    __copyMaterial(mat,ccbObj)

    # 找到所有的底面
    bm = bmesh.new()
    bm.from_mesh(ccbObj.data)
    # -Z轴为向量比较基准
    negZ = Vector((0,0,-1))
    # 选择法线类似的所有面，0.1是在blender里尝试的经验值
    for face in bm.faces:
        # 根据向量的点积判断方向，正为同向，0为垂直，负为反向
        dir = face.normal.dot(negZ)
        if dir > 0.5:
            # 设置为slot1的红漆
            face.material_index = 1
    bm.to_mesh(ccbObj.data)
    bm.free()

    # 展uv
    # 适配仔角梁宽度
    ccbWidth = utils.getMeshDims(ccbObj).y
    UvUnwrap(ccbObj,
             uvType.CUBE,
             cubesize=ccbWidth,
             correctAspect=False)
    return

# 设置山花板
def __setShanhua(shanhuaObj:bpy.types.Object,
             mat:bpy.types.Object):
    # 绑定材质，默认在slot0上，即红漆木板
    __copyMaterial(mat,shanhuaObj)

    # 对山花进行分割，博脊之上做彩画，博脊之下仍为纯红漆木材
    shanghuaTopObj = utils.copySimplyObject(
        shanhuaObj,singleUser=True
    )
    # 裁切
    buildingObj = utils.getAcaParent(
        shanhuaObj,con.ACA_TYPE_BUILDING)
    bData:acaData = buildingObj.ACA_data
    aData:tmpData = bpy.context.scene.ACA_temp
    dk = bData.DK
    scale = dk / con.DEFAULT_DK
    ridgeHeight = aData.ridgeFront_source.dimensions.z * scale
    # 裁剪一个博脊高度，并调整1/4桁径
    offset = (
            con.ROOFMUD_H*dk      # 灰泥
            + ridgeHeight         # 取到博脊上皮
            - con.XYB_WIDTH*dk/2  # 山花厚度加斜
    )
    # 裁剪点
    pCut = shanhuaObj.matrix_world @ Vector((
        0,0,offset))
    utils.addBisect(
        object=shanghuaTopObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_outer=True,
        direction='Y',
        use_fill=False,
    )

    # 找到所有的底面
    bm = bmesh.new()
    bm.from_mesh(shanghuaTopObj.data)
    # X轴为向量比较基准
    negZ = Vector((1,0,0))
    # 选择法线类似的所有面，0.1是在blender里尝试的经验值
    for face in bm.faces:
        # 根据向量的点积判断方向，正为同向，0为垂直，负为反向
        dir = face.normal.dot(negZ)
        if abs(dir) > 0.5:
            # 设置为slot1的山花贴图
            face.material_index = 1
            face.select = True
    bm.to_mesh(shanghuaTopObj.data)
    bm.free()

    # 展uv,满铺拉伸
    UvUnwrap(shanghuaTopObj,
             uvType.CUBE,
             scaleToBounds=True,
             remainSelect=True)
    
    # 裁剪下侧
    utils.addBisect(
        object=shanhuaObj,
        pStart=Vector((0,1,0)),
        pEnd=Vector((0,-1,0)),
        pCut=pCut,
        clear_inner=True,
        direction='Y',
        use_fill=False,
    )
    
    # 合并
    utils.joinObjects([shanhuaObj,shanghuaTopObj],
                      cleanup=True)
    return