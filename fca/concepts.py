""" FCA in pure Python. Only about 6x slower than in C!
   Builds on C. Lindig's Fast Concept Analysis work (1999,2002).
   Copyright (C) 2008-2012 by Dominik Endres.
   dominik.endres@gmail.com
   
   This program is free software; you can redistribute it and/or modify 
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the
   Free Software Foundation, Inc.,
   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
   
   usage example:
           
        relation=[]             
        relation+=[('monkeyHand','neuron2')]
        relation+=[('monkeyFace','neuron1')]
        relation+=[('monkeyFace','neuron2')]
        relation+=[('humanFace','neuron1')]
        relation+=[('spider','neuron3')]

        concepts=formalConcepts(relation)
        concepts.computeLattice()
        print concepts
           
           
   see end of module for more examples.
   
   If you generate publications based on this code, please cite the following paper:

   Endres D., Adam R., Giese M.A. & Noppeney U.. (2012).
   Understanding the Semantic Structure of Human fMRI Brain Recordings with Formal Concept Analysis.
   Proceedings of the 10th International Conference on Formal Concept Analysis (ICFCA 2012) LNAI 7278, Springer,pp. 96-111.

   """


import bisect
import collections
import sys
import gc

import csv

class formalConcept:
        """ A formal concept is comprised of an extent and and intent.
        Furthermore, intentIndexes is an ordered list of attribute indexes for lectic ordering.
        Also contains sets of introduced attibutes and objects and lectically ordered lists of upper and lower neighbours."""
        def __init__(self,extent=frozenset(),intent=frozenset(),intentIndexes=[]):
                """ intent/extent are a frozensets because they need to be hashable."""
                self.cnum=0
                self.extent=extent
                self.intent=intent
                self.introducedAttributes=set()
                self.introducedObjects=set()
                self.intentIndexes=intentIndexes
                self.upperNeighbours=[]
                self.lowerNeighbours=[]
                self.visited=False # for lattice traversal
                
                # attributes that were introduced closest in upwards direction
                # useful for naming a concept that introduces no attributes.
                # recompute after pruning!
                self.closestIntroducedAttributes=[]
                # all attributes that are introduced in the downset of this concept. useful for building search list.
                self.downsetAttributes=set()
                        
                
        def copy(self):
                """Copy construction."""
                ccopy=formalConcept()
                ccopy.cnum=self.cnum
                ccopy.extent=self.extent.copy()
                ccopy.intent=self.intent.copy()
                ccopy.closestIntroducedAttributes=self.closestIntroducedAttributes.copy()
                ccopy.downsetAttributes=self.downsetAttributes.copy()
                ccopy.introducedAttributes=self.introducedAttributes.copy()
                ccopy.introducedObjects=self.introducedObjects.copy()
                ccopy.intentIndexes=self.intentIndexes[:]
                ccopy.upperNeighbours=self.upperNeighbours[:]
                ccopy.lowerNeighbours=self.lowerNeighbours[:]
                ccopy.visited=self.visited
                return ccopy
        
                
        def __cmp__(self,other):
                """lectic order on intentIndexes."""
                if self.intentIndexes==other.intentIndexes:
                        return 0
                i1=0
                i2len=len(other.intentIndexes)
                for a1 in self.intentIndexes:
                        if i1>=i2len:
                                return 1
                        a2=other.intentIndexes[i1]
                        if a1>a2:
                                return -1
                        elif a1<a2:
                                return 1
                        i1+=1
                return -1
        
                
        def __repr__(self):
                """ print the concept."""
                strrep="concept no:"+str(self.cnum)+"\n"
                strrep+="extent:"+repr(self.extent)+"\n"
                strrep+="intent:"+repr(self.intent)+"\n"
                strrep+="introduced objects:"+repr(self.introducedObjects)+"\n"
                strrep+="introduced attributes:"+repr(self.introducedAttributes)+"\n"
                strrep+="upper neighbours: "
                for un in self.upperNeighbours:
                        strrep+=str(un.cnum)+", "
                strrep+="\n"
                strrep+="lower neighbours: "
                for ln in self.lowerNeighbours:
                        strrep+=str(ln.cnum)+", "
                strrep+="\n"
                return strrep
                
        def __hash__(self):
                """A concept is fully identified by its intent, hence the intent hash can serve as concept hash."""
                return self.intent.__hash__()
                
        
                
                
        
class formalContext: 
        """ The formal context.
        Builds dictionaries object=>attributes and vice versa for faster closure computation.
        Set of objects and attributes are kept in lists rather than sets for lectic ordering of concepts.
        """
        def __init__(self,relation,objects=None,attributes=None):
                """ 'relation' has to be an iterable container of tuples. If objects or attributes are not supplied, determine from relation"""
                # map from object=> set of attributes of this object
                self.objectsToAttributes=dict()
                # map from attributes => set of objects of this attribute
                self.attributesToObjects=dict()
                # objects and attributes are kept in lists rather than sets for lectic ordering of concepts.
                self.objects=[]
                self.attributes=[]
                if objects is not None:
                        self.objects=list(objects)
                        for obj in objects: self.objectsToAttributes[obj]=set()
                if attributes is not None:
                        self.attributes=list(attributes)
                        for att in attributes: self.attributesToObjects[att]=set()
                
                for obj,att in relation:
                        if obj not in self.objects:
                                self.objects+=[obj]
                        if att not in self.attributes:
                                self.attributes+=[att]
                        if obj not in self.objectsToAttributes:
                                self.objectsToAttributes[obj]=set([att])
                        else:
                                self.objectsToAttributes[obj].add(att)
                        if att not in self.attributesToObjects:
                                self.attributesToObjects[att]=set([obj])
                        else:
                                self.attributesToObjects[att].add(obj)
                                
                self.attributes.sort()
                self.attributes.reverse()
                                
                
        def objectsPrime(self,objectSet):
                """return a frozenset of all attributes which are shared by members of objectSet."""
                if len(objectSet)==0:
                        return frozenset(self.attributes)
                oiter=iter(objectSet)
                opr=self.objectsToAttributes[oiter.next()].copy()
                for obj in oiter:
                        opr.intersection_update(self.objectsToAttributes[obj])
                return frozenset(opr)
        
        def attributesPrime(self,attributeSet):
                """return a set of all objects which have all attributes in attribute set."""
                if len(attributeSet)==0:
                        return frozenset(self.objects)
                aiter=iter(attributeSet)
                apr=self.attributesToObjects[aiter.next()].copy()
                for att in aiter:
                        apr.intersection_update(self.attributesToObjects[att])
                return frozenset(apr)
                
        def updateIntent(self,intent,object):
                """return intersection of intent and all attributes of object."""
                return frozenset(intent.intersection(self.objectsToAttributes[object]))
        
        def updateExtent(self,extent,attribute):
                """return intersection of intent and all attributes of object."""
                return frozenset(extent.intersection(self.attributesToObjects[attribute]))
        
                
        def indexList(self,attributeSet):
                """return ordered list of attribute indexes. For lectic ordering of concepts."""
                ilist=[]
                for att in attributeSet:
                        ilist+=[self.attributes.index(att)]
                ilist.sort()
                return ilist
                
                

class formalConcepts:
        """ Computes set of concepts from a binary relation by an algorithm similar to C. Lindig's Fast Concept Analysis (2002).
        """
        def __init__(self,relation,objects=None,attributes=None):
                """ 'relation' has to be an iterable container of tuples. If objects or attributes are not supplied, determine from relation."""
                self.context=formalContext(relation,objects,attributes)
                self.concepts=[] # a lectically ordered list of concepts"
                self.intentToConceptDict=dict()
                self.extentToConceptDict=dict()
                
        
                        
        def computeUpperNeighbours(self,concept):
                """ This version of upperNeighbours runs fast enough in Python to be useful.
                Based on a theorem from C. Lindig's (1999) PhD thesis.
                Returns list of upper neighbours of concept."""
                # The set of all objects g which are not in concept's extent G and might therefore be used to create upper neighbours via ((G u g)'',(G u g)')
                upperNeighbourGeneratingObjects=set(self.context.objects).difference(concept.extent)
                # dictionary of intent => set of generating objects
                upperNeighbourCandidates=dict()
                for g in upperNeighbourGeneratingObjects:
                        # an intent of a concept >= concept. Computed by intersecting i(g) with concept.intent,
                        # where i(g) is the set of all attributes of g.
                        intent=self.context.updateIntent(concept.intent,g)
                        # self.intentToConceptDict is a dictionary of all concepts computed so far.
                        if intent in self.intentToConceptDict:
                                curConcept=self.intentToConceptDict[intent]
                                extent=curConcept.extent
                        else:
                                # Store every concept in self.conceptDict, because it will eventually be used
                                # and the closure is expensive to compute
                                extent=self.context.attributesPrime(intent)
                                curConcept=formalConcept(extent,intent,self.context.indexList(intent))
                                self.intentToConceptDict[intent]=curConcept
                                
                        # remember which g generated what concept
                        if intent in upperNeighbourCandidates:
                                upperNeighbourCandidates[intent].add(g)
                        else:
                                upperNeighbourCandidates[intent]=set([g])
                                
                neighbours=[]
                # find all upper neighbours by Lindig's theorem:
                # a concept C=((G u g)'',(G u g)') is an upper neighbour of (G,I) if and only if
                # (G u g)'' \ G = set of all g which generated C.
                for intent,generatingObjects in upperNeighbourCandidates.iteritems():
                        extraObjects=self.intentToConceptDict[intent].extent.difference(concept.extent)
                        if extraObjects==generatingObjects:
                                neighbours+=[self.intentToConceptDict[intent]]
                return neighbours
                        
        def computeLowerNeighbours(self,concept,minsize=0):
                """ This dual version of upperNeighbours runs fast enough in Python to be useful.
                Based on a theorem from C. Lindig's (1999) PhD thesis.
                Returns list of upper neighbours of concept. Ignores lower neighbours with less than minextent objects in extent."""
                # The set of all objects g which are not in concept's extent G and might therefore be used to create upper neighbours via ((G u g)'',(G u g)')
                lowerNeighbourGeneratingAttributes=set(self.context.attributes).difference(concept.intent)
                # dictionary of extent => set of generating attributes
                lowerNeighbourCandidates=dict()
                for i in lowerNeighbourGeneratingAttributes:
                        # an extent of a concept <= concept. Computed by intersecting g(i) with concept.extent,
                        # where g(i) is the set of all objects that have of i.
                        extent=self.context.updateExtent(concept.extent,i)
                        if len(extent)<minsize:
                                continue
                        # self.extentToConceptDict is a dictionary of all concepts computed so far.
                        if extent in self.extentToConceptDict:
                                curConcept=self.extentToConceptDict[extent]
                                intent=curConcept.intent
                        else:
                                # Store every concept in self.conceptDict, because it will eventually be used
                                # and the closure is expensive to compute
                                intent=self.context.objectsPrime(extent)
                                curConcept=formalConcept(extent,intent,self.context.indexList(intent))
                                self.extentToConceptDict[extent]=curConcept
                                
                        # remember which g generated what concept
                        if extent in lowerNeighbourCandidates:
                                lowerNeighbourCandidates[extent].add(i)
                        else:
                                lowerNeighbourCandidates[extent]=set([i])
                                
                neighbours=[]
                # find all lower neighbours by dual of Lindig's theorem:
                # a concept C=((I u i)',(I u i)'') is a lower neighbour of (G,I) if and only if
                # (I u i)'' \ I = set of all i which generated C.
                for extent,generatingAttributes in lowerNeighbourCandidates.iteritems():
                        extraAttributes=self.extentToConceptDict[extent].intent.difference(concept.intent)
                        if extraAttributes==generatingAttributes:
                                neighbours+=[self.extentToConceptDict[extent]]
                        
                
                return neighbours
        
                        
                        
                        
        def numberConceptsAndComputeIntroduced(self):
                """ Numbers concepts and computes introduced objects and attributes"""
                
                numCon=len(self.concepts)
                curConNum=0
                for curConcept in self.concepts:
                        curConcept.cnum=curConNum
                        if curConNum % 1000 == 0: print "computing introduced objects and attributes for concept %d of %d" % (curConNum,numCon)
                        curConcept.upperNeighbours.sort()
                        curConcept.lowerNeighbours.sort()
                        curConcept.introducedObjects=set(curConcept.extent)
                        for ln in curConcept.lowerNeighbours:
                                curConcept.introducedObjects.difference_update(ln.extent)
                        curConcept.introducedAttributes=set(curConcept.intent)
                        for un in curConcept.upperNeighbours:
                                curConcept.introducedAttributes.difference_update(un.intent)
                        curConNum+=1
                print "Done with introduced objects and attributes"
                        
        
        def computeLattice(self):
                """ Computes concepts and lattice.
                self.concepts contains lectically ordered list of concepts after completion."""
                intent=self.context.objectsPrime(set())
                extent=self.context.attributesPrime(intent)
                curConcept=formalConcept(extent,intent,self.context.indexList(intent))
                self.concepts=[curConcept]
                self.intentToConceptDict[curConcept.intent]=curConcept
                curConceptIndex=0
                numComputedConcepts=0
                while True:
                        upperNeighbours=self.computeUpperNeighbours(curConcept)
                        for upperNeighbour in upperNeighbours:
                                upperNeighbourIndex=bisect.bisect(self.concepts,upperNeighbour)
                                if upperNeighbourIndex==0 or self.concepts[upperNeighbourIndex-1]!=upperNeighbour:
                                        self.concepts.insert(upperNeighbourIndex,upperNeighbour)
                                        curConceptIndex+=1
                                                
                                curConcept.upperNeighbours+=[upperNeighbour]
                                upperNeighbour.lowerNeighbours+=[curConcept]
                
                        curConceptIndex-=1
                        if curConceptIndex<0:
                                break
                        curConcept=self.concepts[curConceptIndex]
                        numComputedConcepts+=1
                        if numComputedConcepts % 1000 == 0:
                                print "Computed upper neighbours of %d concepts" % numComputedConcepts,gc.collect()
                                sys.stdout.flush()
                        
                self.numberConceptsAndComputeIntroduced()
                print "Done computing lattice"
                        
                
                        
        def computeMinExtentLattice(self,minextent=0):
                """ Computes concepts and lattice.
                self.concepts contains lectically ordered list of concepts after completion."""
                extent=self.context.attributesPrime(set())
                intent=self.context.objectsPrime(extent)
                curConcept=formalConcept(extent,intent,self.context.indexList(intent))
                self.concepts=[curConcept]
                self.extentToConceptDict[curConcept.extent]=curConcept
                curConceptIndex=0
                numComputedConcepts=0
                while True:
                        lowerNeighbours=self.computeLowerNeighbours(curConcept,minextent)
                        for lowerNeighbour in lowerNeighbours:
                                lowerNeighbourIndex=bisect.bisect(self.concepts,lowerNeighbour)
                                if lowerNeighbourIndex==0 or self.concepts[lowerNeighbourIndex-1]!=lowerNeighbour:
                                        self.concepts.insert(lowerNeighbourIndex,lowerNeighbour)
                                                
                                curConcept.lowerNeighbours+=[lowerNeighbour]
                                lowerNeighbour.upperNeighbours+=[curConcept]
                                
                        curConceptIndex+=1
                        if curConceptIndex>=len(self.concepts):
                                break
                        curConcept=self.concepts[curConceptIndex]
                        numComputedConcepts+=1
                        if numComputedConcepts % 100 == 0:
                                print "Computed lower neighbours of %d concepts" % numComputedConcepts,gc.collect()
                                sys.stdout.flush()
                        
                
                self.numberConceptsAndComputeIntroduced()
                
                        
        def checkLowerNeighbours(self,concept,nonMembers):
                """Helper for checkDownset. Remove all elements from nonMembers which are in the downset of concept."""
                if len(nonMembers)==0:
                        return
                for ln in concept.lowerNeighbours:
                        if not ln.visited:
                                self.checkLowerNeighbours(ln,nonMembers)
                if concept in nonMembers:
                        nonMembers.remove(concept)
                concept.visited=True
                
                        
        def checkDownset(self,topConcept,nonMembers):
                """Remove all elements from nonMembers which are in the downset of topConcept."""
                for con in self.concepts:
                        con.visited=False
                self.checkLowerNeighbours(topConcept,nonMembers)
                
        def enumerateConcepts(self):
                """Assigns numbers to concept based on lectic order."""
                onum=0
                for con in self.concepts:
                        con.cnum=onum
                        onum+=1
                        
        def delConceptFromDicts(self,concept):
                if concept.intent in self.intentToConceptDict:
                        del self.intentToConceptDict[concept.intent]
                if concept.extent in self.extentToConceptDict:
                        del self.extentToConceptDict[concept.extent]
                
                        
        def prune(self,concept,renumber=True):
                """Prune concept from lattice. Upper neighbours are connected to lower neighbours if no other
                path through the lattice connects them. Returns True on success."""
                if concept.intent not in self.intentToConceptDict and concept.extent not in self.extentToConceptDict:
                        return False
                # remove concept from list of lower neighbours of its upper neighbours
                for un in concept.upperNeighbours:
                        ci=bisect.bisect(un.lowerNeighbours,concept)-1
                        if ci>=0 and concept==un.lowerNeighbours[ci]:
                                del un.lowerNeighbours[ci]
                        # objects introduced in concept are now introduced in upper neighbours
                        un.introducedObjects.update(concept.introducedObjects)
                # remove concept from list of upper neighbours of its lower neighbours
                for ln in concept.lowerNeighbours:
                        ci=bisect.bisect(ln.upperNeighbours,concept)-1
                        if ci>=0 and concept==ln.upperNeighbours[ci]:
                                del ln.upperNeighbours[ci]
                        # attributes introduced in concept are now introduced in lower neighbours
                        ln.introducedAttributes.update(concept.introducedAttributes)
                        
                # delete the concepts
                self.delConceptFromDicts(concept)
                ci=bisect.bisect(self.concepts,concept)-1
                if ci>=0 and self.concepts[ci]==concept:
                        del self.concepts[ci]
                        
                # find all lower neighbours of erased concept which are not in the downset of un
                # and add them to the lower neighbours of un
                # and vice versa
                for un in concept.upperNeighbours:
                        lowerNeighbours=concept.lowerNeighbours[:]
                        self.checkDownset(un,lowerNeighbours)
                        un.lowerNeighbours+=lowerNeighbours
                        un.lowerNeighbours.sort()
                        for ln in lowerNeighbours:
                                ci=bisect.insort(ln.upperNeighbours,un)
                                
                # re-number concepts
                if renumber:
                        self.enumerateConcepts()        
                return True
                
        
        def pruneSmallerExtents(self,minNumObjects):
                """Prune all concepts at the bottom of the lattice whose |extent|<=minNumObjects.
                This may lead to some attributes never being introduced! Return number of pruned concepts."""
                oldConNum=len(self.concepts)
                toUpdate=set() # all concepts that need updating of introduced objects after deletion
                for con in self.concepts[:]:
                        if len(con.extent)<minNumObjects:
                                ci=bisect.bisect(self.concepts,con)-1
                                del self.concepts[ci]
                                self.delConceptFromDicts(con)
                                toUpdate.update(con.upperNeighbours) # every upper neighbour of a removed concept is a potential update candidate
                
                toUpdate.intersection_update(self.concepts) # find all update candidates which are still in the set of concepts
                # re-compute introduced objects
                for con in toUpdate:
                        con.introducedObjects=set(con.extent)
                        for ln in con.lowerNeighbours[:]:
                                if ln.intent not in self.intentToConceptDict and ln.extent not in self.extentToConceptDict:
                                        ci=bisect.bisect(con.lowerNeighbours,ln)-1
                                        del con.lowerNeighbours[ci]
                                else:
                                        con.introducedObjects.difference_update(ln.extent)
                # re-number concepts
                self.enumerateConcepts()
                return oldConNum-len(self.concepts)
                                
        def getLowerNeighbours(self,con):
                """ Get all lower neighbours of con. Concept must be in self.concepts!!!"""
                # every concept which is < con in the lectic order is a potential lower neighbour
                lowerNeighbourCandidates=filter(lambda c:c.intent.issuperset(con.intent),self.concepts[self.concepts.index(con)+1:])
                        
                lncs2=set()
                for cc in reversed(lowerNeighbourCandidates):
                        for lnc in lncs2.copy():
                                if cc.intent.issubset(lnc.intent):
                                        lncs2.remove(lnc)
                        lncs2.add(cc)
                        
                lowerNeighbours=list(lncs2)
                lowerNeighbours.sort()
                
                return lowerNeighbours
                                
        def getUpperNeighbours(self,con):
                """ Get all upper neighbours of concept. Concept must be in self.concepts!!!"""
                # every concept which is > con in the lectic order is a potential upper neighbour
                upperNeighbourCandidates=filter(lambda c:c.intent.issubset(con.intent),self.concepts[:self.concepts.index(con)])
                        
                uncs2=set()
                for cc in upperNeighbourCandidates:
                        for unc in uncs2.copy():
                                if cc.intent.issuperset(unc.intent):
                                        uncs2.remove(unc)
                        uncs2.add(cc)
                        
                upperNeighbours=list(uncs2)
                upperNeighbours.sort()
                
                return upperNeighbours
        
                        
                                
                                
        def recomputeNeighbours(self):
                print "recomputing concept order"
                sys.stdout.flush()
                numdone=0
                for con in self.concepts:
                        con.lowerNeighbours=self.getLowerNeighbours(con)
                        con.upperNeighbours=[]
                        numdone+=1
                        if numdone % 100 == 0:
                                print ".",
                                sys.stdout.flush()
                print
                print "%d lower neighbours done. Recomputing upper neighbours." % numdone
                sys.stdout.flush()
                # recompute upper neighbours
                for con in self.concepts:
                        for lcon in con.lowerNeighbours:
                                lcon.upperNeighbours+=[con]
                                
                self.numberConceptsAndComputeIntroduced()
                
                                        
        def pruneNoIntroduced(self,noAttrib=True,noObject=True):
                """Starting from the bottom, prune all concepts that do not introduce at least one attribute (if noAttrib) and/or at least one object (if noObject)
                Leaves top concept. Return number of pruned concepts"""
                oldConNum=len(self.concepts)
                numpruned=0
                prunedConceptList=[]
                for con in self.concepts:
                        if con.cnum==0:
                                prunedConceptList+=[con]
                                continue
                        nia=len(con.introducedAttributes)
                        nio=len(con.introducedObjects)
                        if (nia==0 or not noAttrib) and (nio==0 or not noObject):
                                self.delConceptFromDicts(con)
                                numpruned+=1
                                if numpruned % 100 == 0:
                                        print ".",
                                        sys.stdout.flush()
                        else:
                                prunedConceptList+=[con]
                                

                self.concepts=prunedConceptList
                print
                print "Pruned %d concepts" % numpruned
                self.recomputeNeighbours()
                return numpruned
                                
        def computeAttributeDownsets(self):
                """Iterate through all concepts and compute set of attributes which are introduced in the downset of each concept. Iteration is done in inverse lectic order, therefore each concept needs to check only its immediate subordinates."""
                for con in reversed(self.concepts):
                        con.downsetAttributes=set(con.intent)
                        for ccon in con.lowerNeighbours:
                                con.downsetAttributes.update(ccon.downsetAttributes)
                                
        def computeClosestIntroducedAttributesConcept(self,con,num=5):
                        unlist=[]
                        
                        #con.closestIntroducedAttributes=list(con.intent)
                        #return
                        
                        con.closestIntroducedAttributes=set() #con.introducedAttributes.copy()
                        for uneigh in con.upperNeighbours:
                                unl=list(uneigh.introducedAttributes)+list(uneigh.closestIntroducedAttributes)
                                unlist+=[unl]
                        
                                
                        idx=0
                        foundAnother=len(con.closestIntroducedAttributes)<num
                        while foundAnother:
                                foundAnother=False
                                for unl in unlist:
                                        if len(unl)>idx:
                                                con.closestIntroducedAttributes.add(unl[idx])
                                                foundAnother=True
                                        if len(con.closestIntroducedAttributes)>=num:
                                                break
                                idx+=1
                                if len(con.closestIntroducedAttributes)>=num:
                                        break
                        
                
        
        def computeClosestIntroducedAttributes(self,num=5):
                """Iterate through all concepts and find at most num introduced attributes of closest upper neighbours of. These attributes can then serve as concept name."""
                
                totnum=len(self.concepts)
                i=0
                for curCon in self.concepts:
                        self.computeClosestIntroducedAttributesConcept(curCon,num)
                        i+=1
                        if i%1000 == 0:
                                print "Named %d of %d concepts" % (i,totnum)

                print "Named %d concepts" % totnum
                        
                
                
                
                
                
                                        
        def findClosestIntroducedAttributes(self,concept,num):
                """Find at least num attributes that were introduced closest to concept in upward direction.
                This is useful for naming concepts which introduce no attributes by which they could be named."""
                for con in self.concepts:
                        con.visited=False
                conceptDeque=collections.deque([concept])
                attlist=[]
                while len(conceptDeque)>0 and len(attlist)<=num:
                        curCon=conceptDeque.popleft()
                        if curCon.visited:
                                continue
                        conceptDeque.extend(curCon.upperNeighbours)
                        attlist+=list(curCon.introducedAttributes)
                        curCon.visited=True
                return set(attlist)
                
                
        def findLargestConcept_closure(self,attribList,startConcept):
                """find the largest concept which has all the attributes in attribList, starting at startConcept. Return None if no such concept exists."""
                attSet=set(attribList)
                objSet=self.context.attributesPrime(attSet)
                if len(objSet)==0:
                        # empty extent -- no object matches search
                        print "EMPTY EXTENT"
                        return None
                attSet=self.context.objectsPrime(objSet)
                searchCon=formalConcept(objSet,attSet,self.context.indexList(attSet))
                searchConIndex=bisect.bisect_left(self.concepts,searchCon)
                print "Looking for ",attSet
                print "IDX ",searchConIndex
                if searchConIndex==len(self.concepts):
                        # not found in graph. Could insert instead?
                        return None
                # look for next lower neighbour
                for lnidx in range(searchConIndex,len(self.concepts)):
                        print "CMP ",self.concepts[lnidx].intent," to ",attSet
                        if self.concepts[lnidx].intent.issuperset(attSet):
                                return self.concepts[lnidx]
                        
                # not found in graph. Could insert instead?
                return None
                
        def findLargestConcept(self,attribList,startConcept=None,nextLower=True):
                """find the largest concept which has all the attributes in attribList, starting at startConcept. Return None if no such concept exists."""
                for att in attribList:
                        if att not in self.context.attributesToObjects:
                                return None
                if startConcept is None:
                        startConcept=self.concepts[0]
                attSet=set(attribList)
                searchCon=formalConcept(frozenset([]),attSet,self.context.indexList(attSet))
                searchConIndex=bisect.bisect_left(self.concepts,searchCon,startConcept.cnum)
                #print "Looking for ",attSet
                #print "IDX ",searchConIndex
                if searchConIndex==len(self.concepts):
                        # not found in graph. Could insert instead?
                        return None
                
                if not nextLower:
                        if self.concepts[searchConIndex].intent==attSet:
                                return self.concepts[searchConIndex]
                        else:
                                return None
                        
                # look for next lower neighbour
                for lnidx in range(searchConIndex,len(self.concepts)):
                        #print "CMP ",self.concepts[lnidx].intent," to ",attSet
                        if self.concepts[lnidx].intent.issuperset(attSet):
                                return self.concepts[lnidx]
                        
                # not found in graph. Could insert instead?
                return None
                
        def insertNewConcept(self,attribList,numNames=5):
                """Compute closure of attrib list and insert into graph if extent is not empty. Return new concept or None (if extent is empty). returns tuple (concept,isNew)"""
                for att in attribList:
                        if att not in self.context.attributesToObjects:
                                return (None,False)
                extent=self.context.attributesPrime(set(attribList))
                if len(extent)==0:
                        return (None,False)
                intent=self.context.objectsPrime(extent)
                newCon=formalConcept(extent,intent,self.context.indexList(intent))
                newConIndex=bisect.bisect_left(self.concepts,newCon)
                if newConIndex<len(self.concepts) and self.concepts[newConIndex].intent==intent:
                        # concept already exists
                        print "FOUND ",self.concepts[newConIndex].intent,intent
                        return (self.concepts[newConIndex],False)
                self.concepts.insert(newConIndex,newCon)
                
                # get upper and lower neighbours
                newCon.lowerNeighbours=self.getLowerNeighbours(newCon)
                newCon.upperNeighbours=self.getUpperNeighbours(newCon)
                newCon.introducedAttributes=set(intent)
                newCon.introducedObjects=set(extent)
                # fix parents' lower neighbours and introduced Objects
                for parent in newCon.upperNeighbours:
                        #print "UN ",parent.intent
                        lns=set(parent.lowerNeighbours)
                        lns.difference_update(newCon.lowerNeighbours)
                        lns.add(newCon)
                        parent.lowerNeighbours=list(lns)
                        parent.lowerNeighbours.sort()
                        parent.introducedObjects.difference_update(extent)
                        newCon.introducedAttributes.difference_update(parent.intent)
                        #for ln in parent.lowerNeighbours:
                        #       print "UN-LN ",ln.cnum,ln.intent
                        
                # fix children's upper neighbours and introduced attributes
                for  child in newCon.lowerNeighbours:
                        #print "LN ",parent.intent
                        uns=set(child.upperNeighbours)
                        uns.difference_update(newCon.upperNeighbours)
                        uns.add(newCon)
                        child.upperNeighbours=list(uns)
                        child.upperNeighbours.sort()
                        child.introducedAttributes.difference_update(intent)
                        newCon.introducedObjects.difference_update(child.extent)
                        
                # fix concept numbers
                curidx=0
                for con in self.concepts[curidx:]:
                        con.cnum=curidx
                        curidx+=1
                        
                # fix names of new concept, parents and children
                for con in [newCon]+newCon.lowerNeighbours+newCon.upperNeighbours:
                        self.computeClosestIntroducedAttributesConcept(con,numNames)
                        
                return (newCon,True)


        def dotPrint(self,outStream=sys.stdout,extentView=None,showObjects="all",showAttributes="all",colorlist=None):
                """Print ordered concept set in dot style.
                outStream: open, writeable stream to plot into.
                if extentView(extent,intent) is supplied, it needs to be a function that takes the extent and intent as an argument and
                returns an image filename for it, which will be plotted in the node.
                showObjects,showAttributes= show {all|none|introduced} objects/attributes in the concept nodes.
                colorlist: draw concept boundary in colors from that list, cycle."""
                self.enumerateConcepts()

                if colorlist is None: colorlist=["black"]

                edges=""
                print >> outStream,"digraph lattice {"
                for con in self.concepts:

                    color=colorlist[con.cnum % len(colorlist)]
                        
                    if extentView is not None:
                        extentImg=extentView(con.extent,con.intent)
                        print >> outStream,"node{0:d} [shapefile=\"{1:s}\",label=\"\",color=\"{2:s}\"]".format(con.cnum,extentImg,color)
                    else:
                        if showAttributes=="all": intentStr="\\n".join(map(str,con.intent))
                        elif showAttributes=="introduced": intentStr="\\n".join(map(str,con.introducedAttributes))
                        else: intentStr=""
                        if intentStr[-2:]=="\\n": intentStr=intentStr[:-2]
                        
                        if showObjects=="all": extentStr="\\n".join(map(str,con.extent))
                        elif showObjects=="introduced": extentStr="\\n".join(map(str,con.introducedObjects))
                        else: intentStr=""
                        if extentStr[-2:]=="\\n": extentStr=extentStr[:-2]

                        print >> outStream,"node{0:d} [color={1:s}, shape=Mrecord, style=bold,label=\"{0:02d}|{2:s}|{3:s}\"]".format(con.cnum,color,extentStr,intentStr)

                    for lneigh in con.lowerNeighbours:
                        edges+="node{0:d} -> node{1:d} [color={2:s}]\n".format(con.cnum,lneigh.cnum,colorlist[lneigh.cnum % len(colorlist)])
            
                        
                print >> outStream,edges[:-1]
                print >> outStream,"}"
        
                
                        
        def __repr__(self):
                strrep="Number of concepts: "+str(len(self.concepts))+"\n"
                for cnum in range(len(self.concepts)):
                        if cnum % 10 ==0: print "printing at concept %d of %d " % (cnum,len(self.concepts))
                        strrep+="---------------------------\n"
                        strrep+=repr(self.concepts[cnum])
                        strrep+="naming suggestion:"+reduce(lambda x,y:str(x)+','+str(y),self.findClosestIntroducedAttributes(self.concepts[cnum],3),'')+"\n"
                        strrep+="---------------------------\n"
                print "Returning string representation of lattice"
                return strrep
                
                
        def __getstate__(self):
                """Concepts contain references to parents/children. This may lead to a stack overflow during pickling if the lattice is large. Thus, translate concept references into concept numbers before pickling."""
                
                dictcopy=self.__dict__.copy()
                dictcopy["concepts"]=[]
                dictcopy["intentToConceptDict"]=dict()
                dictcopy["extentToConceptDict"]=dict()
                
                itc=len(self.intentToConceptDict)>0
                etc=len(self.extentToConceptDict)>0
                
                for con in self.concepts:
                        ccopy=con.copy()
                        unn=map(lambda x:x.cnum,ccopy.upperNeighbours)
                        lnn=map(lambda x:x.cnum,ccopy.lowerNeighbours)
                        ccopy.upperNeighbours=unn
                        ccopy.lowerNeighbours=lnn
                        dictcopy["concepts"]+=[ccopy]
                        if itc:
                                dictcopy["intentToConceptDict"][ccopy.intent]=ccopy
                        if etc:
                                dictcopy["extentToConceptDict"][ccopy.extent]=ccopy
                        
                
                        
                
                dictcopy["concepts"].sort()
                return dictcopy
                
        
        def __setstate__(self,thedict):
                """Concepts contain references to parents/children. This may lead to a stack overflow during pickling if the lattice is large. Thus, translate concept references into concept numbers before pickling and vice versa on unpickling."""
                cnumToRefs=dict()
                for con in thedict["concepts"]:
                        cnumToRefs[con.cnum]=con
                
                for con in thedict["concepts"]:
                        unn=map(lambda x:cnumToRefs[x],con.upperNeighbours)
                        lnn=map(lambda x:cnumToRefs[x],con.lowerNeighbours)
                        con.upperNeighbours=unn
                        con.lowerNeighbours=lnn
                self.__dict__=thedict
                
                
if __name__=="__main__":
        
        # some FCA example
        

        # a simple neural code
        relation=[]             
        relation+=[('monkeyHand','n2')]
        relation+=[('monkeyFace','n1')]
        relation+=[('monkeyFace','n2')]
        relation+=[('humanFace','n1')]
        relation+=[('spider','n3')]

        concepts=formalConcepts(relation)
        concepts.computeLattice()
        print "Neural code example"
        print concepts
        print

        # write to dot-file, use colored edges.
        dotfile=open("simpleNeuralCode.dot","w")
        concepts.dotPrint(dotfile,colorlist=["black","red","blue","green"])
        dotfile.close()
        
        conlst=map(lambda x:concepts.concepts[x],[2,3,4,5,1,0])
        for prune in conlst:
                print "Pruning concept ",prune.cnum
                print "-------------------"
                concepts.prune(prune)
                print concepts
                print
                
                
        for prunelimit in range(1,5):
                concepts=formalConcepts(relation)
                concepts.computeLattice()
                print "Pruning all concepts with |extent|<=",prunelimit
                print "-------------------------------------"
                concepts.pruneSmallerExtents(prunelimit)
                print concepts
                print
                
                print "Generating concepts with extent >=",prunelimit
                print "---------------------------------------"
                conbyob=formalConcepts(relation)
                concepts.computeMinExtentLattice(prunelimit+1)
                print concepts
                
   
        # the local code
        relation=[]
        for i in range(10):
                relation+=[(i,i)]

        concepts=formalConcepts(relation)
        concepts.computeMinExtentLattice()
        print "Local code"
        print concepts
        print

        # the 'anti-local' code. produces a boolean lattice
        relation=[]
        for i in range(10):
                for j in range(10):
                        if i!=j:
                                relation+=[(i,j)]

        concepts=formalConcepts(relation)
        concepts.computeMinExtentLattice()
        print "Anti-local code"
        print concepts
        print


        # a random sparse code
        relation=[]
        import random
        import time
        random.seed(123456)


        # write context in colibri-concepts readable format for comparison
        spf=open("sparse.context","w")
        for i in range(1000):
                print >> spf,i,":",
                line=""
                for j in range(1700):
                        if random.random()<10.0/1700:
                                relation+=[(i,j)]
                                line+=str(j)+" "        
                print >> spf,line[:-1]+";"
        spf.close()

                        


        concepts=formalConcepts(relation)
        ct=time.clock()
        concepts.computeLattice()
        ct=time.clock()-ct
        print "Sparse code"
        #print concepts
        print "runtime ",ct
        
        print "Lattice size before deletion of all concepts with less than 10 objects: ",len(concepts.concepts)
        concepts.pruneSmallerExtents(10)
        print "Graph size after deletion of all concepts with less than 10 objects: ",len(concepts.concepts)
        if len(concepts.concepts)!=len(concepts.intentToConceptDict) and len(concepts.concepts)!=len(concepts.extentToConceptDict):
                print "ERROR: concept list length does not match concept dictionary length",len(concepts.concepts),len(concepts.intentToConceptDict),len(concepts.extentToConceptDict)
        for con in concepts.concepts:
                if con.intent not in concepts.intentToConceptDict and con.extent not in concepts.extentToConceptDict:
                        print "ERROR: concept ",con.cnum," not in concept dictionary"
                        
        
                
        conceptsByObj=formalConcepts(relation)
        ct=time.clock()
        conceptsByObj.computeMinExtentLattice(10)
        ct=time.clock()-ct
        print "Sparse code by objects"
        #print conceptsByObj
        print "runtime ",ct
        print "Size of graph without objects having extent <10: ",len(conceptsByObj.concepts)
        
        isOk=True
        for extent,concept in conceptsByObj.extentToConceptDict.iteritems():
                if concepts.intentToConceptDict[concept.intent]!=concept:
                        print "ERROR:",concept
                        isOk=False
        if isOk:
                print "Graphs equal!!!"
        else:
                print "ERROR: graphs NOT equal!!!"

        
        # Lattices for census occupations 1889
        relation = []
        with open('relation-a.csv', 'rb') as csvfile:
                spamreader = csv.reader(csvfile, delimiter=',', quotechar='\"')
                for row in spamreader:
                        relation += [(row[1], row[2])]
        
        concepts=formalConcepts(relation)
        concepts.computeLattice()
        print "Lattice for census occupations 1889"
        print concepts
        print

        # write to dot-file, use colored edges.
        dotfile=open("simpleNeuralCode.dot","w")
        concepts.dotPrint(dotfile,colorlist=["black","red","blue","green"])
        dotfile.close()
        
        # conlst=map(lambda x:concepts.concepts[x],[2,3,4,5,1,0])
        # for prune in conlst:
        #         print "Pruning concept ",prune.cnum
        #         print "-------------------"
        #         concepts.prune(prune)
        #         print concepts
        #         print
                
                
        # for prunelimit in range(1,5):
        #         concepts=formalConcepts(relation)
        #         concepts.computeLattice()
        #         print "Pruning all concepts with |extent|<=",prunelimit
        #         print "-------------------------------------"
        #         concepts.pruneSmallerExtents(prunelimit)
        #         print concepts
        #         print
                
        #         print "Generating concepts with extent >=",prunelimit
        #         print "---------------------------------------"
        #         conbyob=formalConcepts(relation)
        #         concepts.computeMinExtentLattice(prunelimit+1)
        #         print concepts


        # # Lattices for census occupations 1899
        # relation = []
        # with open('relation-b.csv', 'rb') as csvfile:
        #         spamreader = csv.reader(csvfile, delimiter=',', quotechar='\"')
        #         for row in spamreader:
        #                 relation += [(row[1], row[2])]
        
        # concepts=formalConcepts(relation)
        # concepts.computeLattice()
        # print "Lattice for census occupations 1899"
        # print concepts
        # print

        # # write to dot-file, use colored edges.
        # dotfile=open("simpleNeuralCode.dot","w")
        # concepts.dotPrint(dotfile,colorlist=["black","red","blue","green"])
        # dotfile.close()
        
        # conlst=map(lambda x:concepts.concepts[x],[2,3,4,5,1,0])
        # for prune in conlst:
        #         print "Pruning concept ",prune.cnum
        #         print "-------------------"
        #         concepts.prune(prune)
        #         print concepts
        #         print
                
                
        # for prunelimit in range(1,5):
        #         concepts=formalConcepts(relation)
        #         concepts.computeLattice()
        #         print "Pruning all concepts with |extent|<=",prunelimit
        #         print "-------------------------------------"
        #         concepts.pruneSmallerExtents(prunelimit)
        #         print concepts
        #         print
                
        #         print "Generating concepts with extent >=",prunelimit
        #         print "---------------------------------------"
        #         conbyob=formalConcepts(relation)
        #         concepts.computeMinExtentLattice(prunelimit+1)
        #         print concepts

